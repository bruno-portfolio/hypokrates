"""Parser para CSVs cp932 do JADER (PMDA).

Arquivos JADER: demoYYYYMM*.csv, drugYYYYMM*.csv, reacYYYYMM*.csv, histYYYYMM*.csv.
Encoding: cp932 (Shift-JIS). Fallback UTF-8 para golden data / arquivos re-encodados.
"""

from __future__ import annotations

import contextlib
import logging
from pathlib import Path
from typing import TYPE_CHECKING

from hypokrates.jader.constants import ENCODING, FILE_DEMO, FILE_DRUG, FILE_REAC
from hypokrates.jader.mappings import translate_drug, translate_event

if TYPE_CHECKING:
    import io

    from hypokrates.jader.store import JADERStore

logger = logging.getLogger(__name__)


def _open_csv(path: Path) -> io.TextIOWrapper:
    """Abre CSV tentando cp932 primeiro, fallback para UTF-8."""
    try:
        f = open(path, encoding=ENCODING, errors="strict", newline="")  # noqa: SIM115
        f.readline()  # testa leitura
        f.seek(0)
        return f
    except (UnicodeDecodeError, UnicodeError):
        return open(path, encoding="utf-8", errors="replace", newline="")


def _find_jader_file(base_path: Path, prefix: str) -> Path | None:
    """Busca arquivo JADER pelo prefixo (ex: 'demo' → demoYYYYMM*.csv)."""
    # Tentar pattern glob
    matches = sorted(base_path.glob(f"{prefix}*.csv"))
    if matches:
        return matches[0]
    # Tentar case-insensitive
    matches = sorted(base_path.glob(f"{prefix.upper()}*.csv"))
    if matches:
        return matches[0]
    # Tentar nome exato simples (golden data)
    simple = base_path / f"{prefix}.csv"
    if simple.exists():
        return simple
    return None


def load_files_to_store(store: JADERStore, csv_dir: str) -> int:
    """Carrega todos os CSVs JADER no DuckDB store.

    Returns:
        Número de reports carregados.
    """
    base_path = Path(csv_dir)

    # Limpar tabelas
    for table in ("jader_dedup", "jader_reac", "jader_drug", "jader_demo"):
        store.execute_in_lock(f"DELETE FROM {table}")

    total_reports = 0

    # 1. Demo
    demo_path = _find_jader_file(base_path, FILE_DEMO)
    if demo_path:
        total_reports = _load_demo(store, demo_path)
        logger.info("JADER: loaded %d demo records", total_reports)
    else:
        logger.warning("JADER: demo file not found in %s", csv_dir)

    # 2. Drug (com tradução JP→EN)
    drug_path = _find_jader_file(base_path, FILE_DRUG)
    if drug_path:
        count = _load_drug(store, drug_path)
        logger.info("JADER: loaded %d drug records", count)
    else:
        logger.warning("JADER: drug file not found in %s", csv_dir)

    # 3. Reac (com tradução JP→EN)
    reac_path = _find_jader_file(base_path, FILE_REAC)
    if reac_path:
        count = _load_reac(store, reac_path)
        logger.info("JADER: loaded %d reaction records", count)
    else:
        logger.warning("JADER: reac file not found in %s", csv_dir)

    # 4. Build dedup table
    _build_dedup(store)

    dedup_count = _count_table(store, "jader_dedup")
    logger.info("JADER load complete: %d reports (%d deduplicated)", total_reports, dedup_count)
    return dedup_count


def _load_demo(store: JADERStore, path: Path) -> int:
    """Carrega demo CSV via Python csv.reader (cp932 nativo).

    Colunas JADER demo (com header JP):
    0: 識別番号 (case_id)
    1: 報告回数 (report_version)
    2: 性別 (sex)
    3: 年齢 (age_group)
    4: 体重 (weight)
    5: 報告者 (reporter_qual)
    """
    import csv

    rows: list[list[object]] = []
    with _open_csv(path) as f:
        reader = csv.reader(f)
        next(reader, None)  # skip header

        for row in reader:
            if len(row) < 2 or not row[0].strip():
                continue
            case_id = row[0].strip()
            version = 1
            with contextlib.suppress(ValueError):
                version = int(row[1].strip()) if row[1].strip() else 1
            sex = row[2].strip() if len(row) > 2 else ""
            age_group = row[3].strip() if len(row) > 3 else ""
            weight = row[4].strip() if len(row) > 4 else ""
            reporter = row[5].strip() if len(row) > 5 else ""
            rows.append([case_id, version, sex, age_group, weight, reporter])

    if rows:
        store.executemany_in_lock(
            "INSERT INTO jader_demo VALUES ($1, $2, $3, $4, $5, $6)",
            rows,
        )
    return len(rows)


def _load_drug(store: JADERStore, path: Path) -> int:
    """Carrega drug CSV com tradução JP→EN via Python (batch insert).

    Colunas JADER drug (com header JP):
    0: 識別番号 (case_id)
    1: 報告回数 (report_version)
    2: 医薬品(一般名) (drug_name_jp / generic)
    3: 医薬品(販売名) (brand_name_jp)
    4: 医薬品の関与 (drug_role)
    """
    import csv

    rows: list[list[object]] = []
    with _open_csv(path) as f:
        reader = csv.reader(f)
        header = next(reader, None)  # skip header
        if header is None:
            return 0

        for row in reader:
            if len(row) < 5 or not row[0].strip():
                continue
            case_id = row[0].strip()
            version = 1
            with contextlib.suppress(ValueError):
                version = int(row[1].strip()) if row[1].strip() else 1
            drug_jp = row[2].strip()
            brand_jp = row[3].strip()
            role = row[4].strip()

            drug_en, confidence = translate_drug(drug_jp)
            rows.append([case_id, version, drug_jp, drug_en, confidence.value, brand_jp, role])

    if rows:
        store.executemany_in_lock(
            "INSERT INTO jader_drug VALUES ($1, $2, $3, $4, $5, $6, $7)",
            rows,
        )
    return len(rows)


def _load_reac(store: JADERStore, path: Path) -> int:
    """Carrega reac CSV com tradução JP→EN via Python (batch insert).

    Colunas JADER reac (com header JP):
    0: 識別番号 (case_id)
    1: 報告回数 (report_version)
    2: 有害事象 (pt_jp — MedDRA/J)
    3: 転帰 (outcome)
    """
    import csv

    rows: list[list[object]] = []
    with _open_csv(path) as f:
        reader = csv.reader(f)
        next(reader, None)  # skip header

        for row in reader:
            if len(row) < 3 or not row[0].strip():
                continue
            case_id = row[0].strip()
            version = 1
            with contextlib.suppress(ValueError):
                version = int(row[1].strip()) if row[1].strip() else 1
            pt_jp = row[2].strip()
            outcome = row[3].strip() if len(row) > 3 else ""

            pt_en, confidence = translate_event(pt_jp)
            rows.append([case_id, version, pt_jp, pt_en, confidence.value, outcome])

    if rows:
        store.executemany_in_lock(
            "INSERT INTO jader_reac VALUES ($1, $2, $3, $4, $5, $6)",
            rows,
        )
    return len(rows)


def _build_dedup(store: JADERStore) -> None:
    """Deduplicação: max(report_version) per case_id."""
    store.execute_in_lock(
        """
        INSERT INTO jader_dedup
        SELECT case_id, MAX(report_version)
        FROM jader_demo
        GROUP BY case_id
        """
    )


def _count_table(store: JADERStore, table: str) -> int:
    """Conta registros em uma tabela."""
    rows = store.query_in_lock(f"SELECT COUNT(*) FROM {table}")
    if rows and rows[0]:
        count = rows[0][0]
        return int(count) if isinstance(count, (int, float, str)) else 0
    return 0
