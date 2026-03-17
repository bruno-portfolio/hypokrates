"""Parser para CSVs cp932 do JADER (PMDA).

Arquivos JADER: demoYYYYMM*.csv, drugYYYYMM*.csv, reacYYYYMM*.csv, histYYYYMM*.csv.
Encoding: cp932 (Shift-JIS). Estrategia: transcode cp932→UTF-8, depois DuckDB read_csv nativo.
Golden data (ja UTF-8) detectada automaticamente.
"""

from __future__ import annotations

import logging
import tempfile
from pathlib import Path
from typing import TYPE_CHECKING

from hypokrates.jader.constants import ENCODING, FILE_DEMO, FILE_DRUG, FILE_REAC
from hypokrates.jader.mappings import DRUG_JP_EN, MEDDRA_JP_EN

if TYPE_CHECKING:
    from hypokrates.jader.store import JADERStore

logger = logging.getLogger(__name__)


def _find_jader_file(base_path: Path, prefix: str) -> Path | None:
    """Busca arquivo JADER pelo prefixo (ex: 'demo' -> demoYYYYMM*.csv)."""
    matches = sorted(base_path.glob(f"{prefix}*.csv"))
    if matches:
        return matches[0]
    matches = sorted(base_path.glob(f"{prefix.upper()}*.csv"))
    if matches:
        return matches[0]
    simple = base_path / f"{prefix}.csv"
    if simple.exists():
        return simple
    return None


def _is_cp932(path: Path) -> bool:
    """Detecta se arquivo e cp932 (vs UTF-8)."""
    try:
        with open(path, encoding="utf-8", errors="strict") as f:
            f.readline()
        return False
    except UnicodeDecodeError:
        return True


def _transcode_to_utf8(path: Path) -> Path:
    """Transcode cp932 -> UTF-8 via iconv (C nativo) ou fallback Python."""
    import shutil
    import subprocess

    tmp = Path(tempfile.mktemp(suffix=".csv"))

    if shutil.which("iconv"):
        subprocess.run(
            ["iconv", "-f", "CP932", "-t", "UTF-8", str(path)],
            stdout=open(tmp, "w", encoding="utf-8"),  # noqa: SIM115
            check=True,
        )
    else:
        with (
            open(path, encoding=ENCODING, errors="replace") as fin,
            open(tmp, "w", encoding="utf-8") as fout,
        ):
            for line in fin:
                fout.write(line)
    return tmp


def _ensure_utf8(path: Path) -> tuple[Path, bool]:
    """Retorna (path_utf8, is_temp). Se ja e UTF-8, retorna o original."""
    if _is_cp932(path):
        logger.info("JADER: transcoding %s cp932 -> utf8...", path.name)
        return _transcode_to_utf8(path), True
    return path, False


def load_files_to_store(store: JADERStore, csv_dir: str) -> int:
    """Carrega todos os CSVs JADER no DuckDB store.

    Returns:
        Numero de reports deduplicated.
    """
    base_path = Path(csv_dir)

    for table in ("jader_dedup", "jader_reac", "jader_drug", "jader_demo"):
        store.execute_in_lock(f"DELETE FROM {table}")

    total_reports = 0

    demo_path = _find_jader_file(base_path, FILE_DEMO)
    if demo_path:
        total_reports = _load_demo(store, demo_path)
        logger.info("JADER: loaded %d demo records", total_reports)
    else:
        logger.warning("JADER: demo file not found in %s", csv_dir)

    drug_path = _find_jader_file(base_path, FILE_DRUG)
    if drug_path:
        count = _load_drug(store, drug_path)
        logger.info("JADER: loaded %d drug records", count)
    else:
        logger.warning("JADER: drug file not found in %s", csv_dir)

    reac_path = _find_jader_file(base_path, FILE_REAC)
    if reac_path:
        count = _load_reac(store, reac_path)
        logger.info("JADER: loaded %d reaction records", count)
    else:
        logger.warning("JADER: reac file not found in %s", csv_dir)

    _build_dedup(store)

    dedup_count = _count_table(store, "jader_dedup")
    logger.info("JADER load complete: %d reports (%d deduplicated)", total_reports, dedup_count)
    return dedup_count


def _load_demo(store: JADERStore, path: Path) -> int:
    """Carrega demo via DuckDB read_csv (transcode se cp932).

    Colunas: 0:case_id, 1:version, 2:sex, 3:age, 4:weight, 9:reporter_qual
    """
    utf8_path, is_temp = _ensure_utf8(path)
    try:
        escaped = str(utf8_path).replace("'", "''").replace("\\", "/")
        store.execute_in_lock(f"""
            INSERT INTO jader_demo (case_id, report_version, sex, age_group, weight, reporter_qual)
            SELECT
                TRIM(c0),
                COALESCE(TRY_CAST(TRIM(c1) AS INTEGER), 1),
                COALESCE(TRIM(c2), ''),
                COALESCE(TRIM(c3), ''),
                COALESCE(TRIM(c4), ''),
                COALESCE(TRIM(c9), '')
            FROM read_csv('{escaped}',
                header=false, skip=1, all_varchar=true,
                ignore_errors=true, null_padding=true,
                names=['c0','c1','c2','c3','c4','c5','c6','c7','c8','c9','c10'])
            WHERE c0 IS NOT NULL AND TRIM(c0) != ''
        """)
    finally:
        if is_temp:
            utf8_path.unlink(missing_ok=True)
    return _count_table(store, "jader_demo")


def _load_drug(store: JADERStore, path: Path) -> int:
    """Carrega drug via DuckDB read_csv + UPDATE para traducao JP->EN.

    Colunas: 0:case_id, 1:version, 3:role, 4:generic_jp, 5:brand_jp
    """
    utf8_path, is_temp = _ensure_utf8(path)
    try:
        escaped = str(utf8_path).replace("'", "''").replace("\\", "/")
        store.execute_in_lock(f"""
            INSERT INTO jader_drug
                (case_id, report_version, drug_name_jp, drug_name_en,
                 drug_confidence, brand_name_jp, drug_role)
            SELECT
                TRIM(c0),
                COALESCE(TRY_CAST(TRIM(c1) AS INTEGER), 1),
                COALESCE(TRIM(c4), ''),
                '',
                'unmapped',
                COALESCE(TRIM(c5), ''),
                COALESCE(TRIM(c3), '')
            FROM read_csv('{escaped}',
                header=false, skip=1, all_varchar=true,
                ignore_errors=true, null_padding=true,
                names=['c0','c1','c2','c3','c4','c5','c6','c7','c8','c9',
                       'c10','c11','c12','c13','c14','c15'])
            WHERE c0 IS NOT NULL AND TRIM(c0) != ''
        """)
    finally:
        if is_temp:
            utf8_path.unlink(missing_ok=True)

    _apply_drug_translations(store)
    return _count_table(store, "jader_drug")


def _load_reac(store: JADERStore, path: Path) -> int:
    """Carrega reac via DuckDB read_csv + UPDATE para traducao JP->EN.

    Colunas: 0:case_id, 1:version, 3:pt_jp, 4:outcome
    """
    utf8_path, is_temp = _ensure_utf8(path)
    try:
        escaped = str(utf8_path).replace("'", "''").replace("\\", "/")
        store.execute_in_lock(f"""
            INSERT INTO jader_reac
                (case_id, report_version, pt_jp, pt_en, event_confidence, outcome)
            SELECT
                TRIM(c0),
                COALESCE(TRY_CAST(TRIM(c1) AS INTEGER), 1),
                COALESCE(TRIM(c3), ''),
                '',
                'unmapped',
                COALESCE(TRIM(c4), '')
            FROM read_csv('{escaped}',
                header=false, skip=1, all_varchar=true,
                ignore_errors=true, null_padding=true,
                names=['c0','c1','c2','c3','c4','c5'])
            WHERE c0 IS NOT NULL AND TRIM(c0) != ''
        """)
    finally:
        if is_temp:
            utf8_path.unlink(missing_ok=True)

    _apply_event_translations(store)
    return _count_table(store, "jader_reac")


def _apply_drug_translations(store: JADERStore) -> None:
    """Aplica traducoes JP->EN via tabela temporaria + JOIN (1 UPDATE)."""
    # Criar tabela de mapeamento
    store.execute_in_lock("DROP TABLE IF EXISTS _tmp_drug_map")
    store.execute_in_lock(
        "CREATE TEMP TABLE _tmp_drug_map (jp VARCHAR PRIMARY KEY, en VARCHAR NOT NULL)"
    )
    map_rows: list[list[object]] = [[jp, en] for jp, en in DRUG_JP_EN.items()]
    store.executemany_in_lock("INSERT INTO _tmp_drug_map VALUES ($1, $2)", map_rows)

    # 1. Exact: JOIN com tabela de mapeamento
    store.execute_in_lock("""
        UPDATE jader_drug SET
            drug_name_en = m.en,
            drug_confidence = 'exact'
        FROM _tmp_drug_map m
        WHERE jader_drug.drug_name_jp = m.jp
    """)

    # 2. Inferred: ASCII/romaji (sem caracteres nao-ASCII)
    store.execute_in_lock("""
        UPDATE jader_drug SET
            drug_name_en = UPPER(drug_name_jp),
            drug_confidence = 'inferred'
        WHERE drug_confidence = 'unmapped'
        AND drug_name_jp != ''
        AND drug_name_jp = regexp_replace(drug_name_jp, '[^ -~]', '', 'g')
    """)

    # 3. Unmapped: uppercase do original
    store.execute_in_lock("""
        UPDATE jader_drug SET drug_name_en = UPPER(drug_name_jp)
        WHERE drug_confidence = 'unmapped' AND drug_name_jp != ''
    """)

    store.execute_in_lock("DROP TABLE IF EXISTS _tmp_drug_map")


def _apply_event_translations(store: JADERStore) -> None:
    """Aplica traducoes JP->EN via tabela temporaria + JOIN (1 UPDATE)."""
    store.execute_in_lock("DROP TABLE IF EXISTS _tmp_event_map")
    store.execute_in_lock(
        "CREATE TEMP TABLE _tmp_event_map (jp VARCHAR PRIMARY KEY, en VARCHAR NOT NULL)"
    )
    map_rows: list[list[object]] = [[jp, en] for jp, en in MEDDRA_JP_EN.items()]
    store.executemany_in_lock("INSERT INTO _tmp_event_map VALUES ($1, $2)", map_rows)

    # 1. Exact: JOIN
    store.execute_in_lock("""
        UPDATE jader_reac SET
            pt_en = m.en,
            event_confidence = 'exact'
        FROM _tmp_event_map m
        WHERE jader_reac.pt_jp = m.jp
    """)

    # 2. Inferred: ASCII/romaji
    store.execute_in_lock("""
        UPDATE jader_reac SET
            pt_en = UPPER(pt_jp),
            event_confidence = 'inferred'
        WHERE event_confidence = 'unmapped'
        AND pt_jp != ''
        AND pt_jp = regexp_replace(pt_jp, '[^ -~]', '', 'g')
    """)

    # 3. Unmapped: uppercase do original
    store.execute_in_lock("""
        UPDATE jader_reac SET pt_en = UPPER(pt_jp)
        WHERE event_confidence = 'unmapped' AND pt_jp != ''
    """)

    store.execute_in_lock("DROP TABLE IF EXISTS _tmp_event_map")


def _build_dedup(store: JADERStore) -> None:
    """Deduplicacao: max(report_version) per case_id."""
    store.execute_in_lock("""
        INSERT INTO jader_dedup
        SELECT case_id, MAX(report_version)
        FROM jader_demo
        GROUP BY case_id
    """)


def _count_table(store: JADERStore, table: str) -> int:
    """Conta registros em uma tabela."""
    rows = store.query_in_lock(f"SELECT COUNT(*) FROM {table}")
    if rows and rows[0]:
        count = rows[0][0]
        return int(count) if isinstance(count, (int, float, str)) else 0
    return 0
