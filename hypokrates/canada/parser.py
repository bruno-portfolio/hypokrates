"""Parser para arquivos $-delimited do Canada Vigilance.

Os arquivos bulk do Canada Vigilance NÃO possuem header row.
Usamos csv.reader com acesso posicional (índice de coluna).

Posições documentadas em:
https://www.canada.ca/en/health-canada/services/drugs-health-products/
medeffect-canada/adverse-reaction-database/read-file-layouts.html
"""

from __future__ import annotations

import csv
import logging
from pathlib import Path
from typing import TYPE_CHECKING

from hypokrates.canada.constants import (
    DELIMITER,
    FILE_DRUG_INGREDIENTS,
    FILE_DRUG_PRODUCT,
    FILE_REACTIONS,
    FILE_REPORT_DRUG,
    FILE_REPORTS,
)

if TYPE_CHECKING:
    from collections.abc import Iterator

    from hypokrates.canada.store import CanadaVigilanceStore

logger = logging.getLogger(__name__)

# Batch size para inserts
_BATCH_SIZE = 5000


def _find_file(base_path: Path, primary: str, *alternates: str) -> Path | None:
    """Busca arquivo por nome, tentando alternativas (case-insensitive no Windows).

    Alguns extracts do Canada Vigilance usam nomes diferentes
    (e.g., ``Drug_Product.txt`` vs ``drug_products.txt``).
    """
    for name in (primary, *alternates):
        candidate = base_path / name
        if candidate.exists():
            return candidate
    return None


def load_files_to_store(store: CanadaVigilanceStore, csv_dir: str) -> int:
    """Carrega todos os arquivos do Canada Vigilance no DuckDB store.

    Args:
        store: CanadaVigilanceStore instance.
        csv_dir: Diretório contendo os arquivos extraídos do ZIP.

    Returns:
        Número de reports carregados.
    """
    base_path = Path(csv_dir)

    # Limpar tabelas
    for table in (
        "canada_ingredients",
        "canada_products",
        "canada_reactions",
        "canada_drugs",
        "canada_dedup",
        "canada_reports",
    ):
        store.execute_in_lock(f"DELETE FROM {table}")

    total_reports = 0

    # 1. Reports
    reports_path = _find_file(base_path, FILE_REPORTS, "reports.txt")
    if reports_path:
        total_reports = _load_reports(store, reports_path)
        logger.info("Canada: loaded %d reports", total_reports)
    else:
        logger.warning("Canada: Reports file not found in %s", csv_dir)

    # 2. Report_Drug
    drugs_path = _find_file(base_path, FILE_REPORT_DRUG, "report_drug.txt")
    if drugs_path:
        count = _load_report_drugs(store, drugs_path)
        logger.info("Canada: loaded %d drug records", count)

    # 3. Reactions
    reactions_path = _find_file(base_path, FILE_REACTIONS, "reactions.txt")
    if reactions_path:
        count = _load_reactions(store, reactions_path)
        logger.info("Canada: loaded %d reaction records", count)

    # 4. Drug_Product (pode ser drug_products.txt em alguns extracts)
    products_path = _find_file(
        base_path, FILE_DRUG_PRODUCT, "drug_products.txt", "Drug_Products.txt"
    )
    if products_path:
        count = _load_products(store, products_path)
        logger.info("Canada: loaded %d products", count)

    # 5. Drug_Product_Ingredients
    ingredients_path = _find_file(base_path, FILE_DRUG_INGREDIENTS, "drug_product_ingredients.txt")
    if ingredients_path:
        count = _load_ingredients(store, ingredients_path)
        logger.info("Canada: loaded %d ingredients", count)

    logger.info("Canada Vigilance load complete: %d reports", total_reports)
    return total_reports


def _read_rows(path: Path) -> Iterator[list[str]]:
    """Lê arquivo $-delimited como csv.reader (sem header)."""
    fh = path.open(encoding="utf-8", errors="replace")
    yield from csv.reader(fh, delimiter=DELIMITER, quotechar='"')


def _safe_int(val: str, default: int = 0) -> int:
    """Converte string para int com fallback."""
    val = val.strip()
    if not val:
        return default
    try:
        return int(val)
    except ValueError:
        return default


def _col(row: list[str], idx: int) -> str:
    """Acessa coluna por índice com fallback para string vazia."""
    if idx < len(row):
        return row[idx]
    return ""


# ── Reports.txt ──────────────────────────────────────────────
# Col 0: REPORT_ID, 3: DATRECEIVED, 9: GENDER_CODE,
# 12: AGE, 16: OUTCOME_CODE, 25: SERIOUSNESS_CODE


def _load_reports(store: CanadaVigilanceStore, path: Path) -> int:
    """Carrega Reports.txt."""
    rows: list[list[object]] = []
    count = 0

    for record in _read_rows(path):
        report_id = _safe_int(_col(record, 0))
        if report_id == 0:
            continue
        rows.append(
            [
                report_id,
                _col(record, 3).strip(),  # DATRECEIVED
                _col(record, 9).strip(),  # GENDER_CODE
                _col(record, 12).strip(),  # AGE
                _col(record, 16).strip(),  # OUTCOME_CODE
                _col(record, 25).strip(),  # SERIOUSNESS_CODE
            ]
        )
        if len(rows) >= _BATCH_SIZE:
            store.executemany_in_lock("INSERT INTO canada_reports VALUES (?, ?, ?, ?, ?, ?)", rows)
            count += len(rows)
            rows = []

    if rows:
        store.executemany_in_lock("INSERT INTO canada_reports VALUES (?, ?, ?, ?, ?, ?)", rows)
        count += len(rows)

    return count


# ── Report_Drug.txt ──────────────────────────────────────────
# Col 0: REPORT_DRUG_ID, 1: REPORT_ID, 2: DRUG_PRODUCT_ID,
# 3: DRUGNAME, 4: DRUGINVOLV_ENG


def _load_report_drugs(store: CanadaVigilanceStore, path: Path) -> int:
    """Carrega Report_Drug.txt."""
    rows: list[list[object]] = []
    count = 0

    for record in _read_rows(path):
        report_id = _safe_int(_col(record, 1))
        if report_id == 0:
            continue
        rows.append(
            [
                _safe_int(_col(record, 0)),  # REPORT_DRUG_ID
                report_id,  # REPORT_ID
                _safe_int(_col(record, 2)),  # DRUG_PRODUCT_ID
                _col(record, 4).strip(),  # DRUGINVOLV_ENG
            ]
        )
        if len(rows) >= _BATCH_SIZE:
            store.executemany_in_lock("INSERT INTO canada_drugs VALUES (?, ?, ?, ?)", rows)
            count += len(rows)
            rows = []

    if rows:
        store.executemany_in_lock("INSERT INTO canada_drugs VALUES (?, ?, ?, ?)", rows)
        count += len(rows)

    return count


# ── Reactions.txt ────────────────────────────────────────────
# Col 0: REACTION_ID, 1: REPORT_ID, 2: DURATION,
# 3: DURATION_UNIT_ENG, 4: DURATION_UNIT_FR,
# 5: PT_NAME_ENG, 7: SOC_NAME_ENG, 9: MEDDRA_VERSION


def _load_reactions(store: CanadaVigilanceStore, path: Path) -> int:
    """Carrega Reactions.txt."""
    rows: list[list[object]] = []
    count = 0

    for record in _read_rows(path):
        report_id = _safe_int(_col(record, 1))
        if report_id == 0:
            continue
        rows.append(
            [
                _safe_int(_col(record, 0)),  # REACTION_ID
                report_id,  # REPORT_ID
                _col(record, 5).strip(),  # PT_NAME_ENG
                _col(record, 7).strip(),  # SOC_NAME_ENG
                _col(record, 9).strip(),  # MEDDRA_VERSION
            ]
        )
        if len(rows) >= _BATCH_SIZE:
            store.executemany_in_lock("INSERT INTO canada_reactions VALUES (?, ?, ?, ?, ?)", rows)
            count += len(rows)
            rows = []

    if rows:
        store.executemany_in_lock("INSERT INTO canada_reactions VALUES (?, ?, ?, ?, ?)", rows)
        count += len(rows)

    return count


# ── Drug_Product.txt / drug_products.txt ─────────────────────
# Col 0: DRUG_PRODUCT_ID, 1: DRUGNAME


def _load_products(store: CanadaVigilanceStore, path: Path) -> int:
    """Carrega Drug_Product.txt."""
    rows: list[list[object]] = []
    count = 0

    for record in _read_rows(path):
        product_id = _safe_int(_col(record, 0))
        if product_id == 0:
            continue
        rows.append(
            [
                product_id,
                _col(record, 1).strip(),  # DRUGNAME
            ]
        )
        if len(rows) >= _BATCH_SIZE:
            store.executemany_in_lock("INSERT INTO canada_products VALUES (?, ?)", rows)
            count += len(rows)
            rows = []

    if rows:
        store.executemany_in_lock("INSERT INTO canada_products VALUES (?, ?)", rows)
        count += len(rows)

    return count


# ── Drug_Product_Ingredients.txt ─────────────────────────────
# Col 0: LINK_ID(?), 1: DRUG_PRODUCT_ID, 2: DRUGNAME,
# 3: INGREDIENT_ID(?), 4: ACTIVE_INGREDIENT_NAME


def _load_ingredients(store: CanadaVigilanceStore, path: Path) -> int:
    """Carrega Drug_Product_Ingredients.txt (5 colunas)."""
    rows: list[list[object]] = []
    count = 0

    for record in _read_rows(path):
        product_id = _safe_int(_col(record, 1))
        if product_id == 0:
            continue
        rows.append(
            [
                product_id,
                _col(record, 4).strip(),  # ACTIVE_INGREDIENT_NAME
            ]
        )
        if len(rows) >= _BATCH_SIZE:
            store.executemany_in_lock("INSERT INTO canada_ingredients VALUES (?, ?)", rows)
            count += len(rows)
            rows = []

    if rows:
        store.executemany_in_lock("INSERT INTO canada_ingredients VALUES (?, ?)", rows)
        count += len(rows)

    return count
