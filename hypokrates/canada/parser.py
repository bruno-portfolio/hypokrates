"""Parser para arquivos $-delimited do Canada Vigilance.

Os arquivos bulk do Canada Vigilance NÃO possuem header row.
Usamos DuckDB read_csv() nativo para performance (~100x mais rápido que csv.reader).

Posições documentadas em:
https://www.canada.ca/en/health-canada/services/drugs-health-products/
medeffect-canada/adverse-reaction-database/read-file-layouts.html
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import TYPE_CHECKING

from hypokrates.canada.constants import (
    FILE_DRUG_INGREDIENTS,
    FILE_DRUG_PRODUCT,
    FILE_REACTIONS,
    FILE_REPORT_DRUG,
    FILE_REPORTS,
)

if TYPE_CHECKING:
    from hypokrates.canada.store import CanadaVigilanceStore

logger = logging.getLogger(__name__)


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


def _csv_opts(path: Path, *, null_padding: bool = False) -> str:
    """Monta opções comuns do read_csv para arquivos $-delimited."""
    escaped = str(path).replace("'", "''")
    extra = ""
    if null_padding:
        extra = ", null_padding=true, parallel=false, strict_mode=false"
    return (
        f"read_csv('{escaped}', "
        f"delim='$', header=false, all_varchar=true, "
        f"ignore_errors=true, quote='\"'{extra})"
    )


def load_files_to_store(store: CanadaVigilanceStore, csv_dir: str) -> int:
    """Carrega todos os arquivos do Canada Vigilance no DuckDB store.

    Usa DuckDB read_csv() nativo para máxima performance.

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
    else:
        logger.warning("Canada: Report_Drug file not found in %s", csv_dir)

    # 3. Reactions
    reactions_path = _find_file(base_path, FILE_REACTIONS, "reactions.txt")
    if reactions_path:
        count = _load_reactions(store, reactions_path)
        logger.info("Canada: loaded %d reaction records", count)
    else:
        logger.warning("Canada: Reactions file not found in %s", csv_dir)

    # 4. Drug_Product
    products_path = _find_file(
        base_path, FILE_DRUG_PRODUCT, "drug_products.txt", "Drug_Products.txt"
    )
    if products_path:
        count = _load_products(store, products_path)
        logger.info("Canada: loaded %d products", count)
    else:
        logger.warning("Canada: Drug_Product file not found in %s", csv_dir)

    # 5. Drug_Product_Ingredients
    ingredients_path = _find_file(base_path, FILE_DRUG_INGREDIENTS, "drug_product_ingredients.txt")
    if ingredients_path:
        count = _load_ingredients(store, ingredients_path)
        logger.info("Canada: loaded %d ingredients", count)
    else:
        logger.warning("Canada: Drug_Product_Ingredients file not found in %s", csv_dir)

    logger.info("Canada Vigilance load complete: %d reports", total_reports)
    return total_reports


# ── Reports.txt ──────────────────────────────────────────────
# Col 0: REPORT_ID, 3: DATRECEIVED, 9: GENDER_CODE,
# 12: AGE, 16: OUTCOME_CODE, 25: SERIOUSNESS_CODE


def _load_reports(store: CanadaVigilanceStore, path: Path) -> int:
    """Carrega Reports.txt via DuckDB read_csv().

    42 colunas → DuckDB zero-pads: column00..column41.
    """
    src = _csv_opts(path)
    sql = f"""
        INSERT INTO canada_reports
        SELECT
            TRY_CAST(column00 AS INTEGER),
            TRIM(column03),
            TRIM(column09),
            TRIM(column12),
            TRIM(column16),
            TRIM(column25)
        FROM {src}
        WHERE TRY_CAST(column00 AS INTEGER) IS NOT NULL
          AND TRY_CAST(column00 AS INTEGER) > 0
    """
    store.execute_in_lock(sql)
    return _count_table(store, "canada_reports")


# ── Report_Drug.txt ──────────────────────────────────────────
# Col 0: REPORT_DRUG_ID, 1: REPORT_ID, 2: DRUG_PRODUCT_ID,
# 3: DRUGNAME, 4: DRUGINVOLV_ENG


def _load_report_drugs(store: CanadaVigilanceStore, path: Path) -> int:
    """Carrega Report_Drug.txt via DuckDB read_csv().

    22 colunas → DuckDB zero-pads: column00..column21.
    """
    src = _csv_opts(path)
    sql = f"""
        INSERT INTO canada_drugs
        SELECT
            TRY_CAST(column00 AS INTEGER),
            TRY_CAST(column01 AS INTEGER),
            COALESCE(TRY_CAST(column02 AS INTEGER), 0),
            TRIM(column04)
        FROM {src}
        WHERE TRY_CAST(column01 AS INTEGER) IS NOT NULL
          AND TRY_CAST(column01 AS INTEGER) > 0
    """
    store.execute_in_lock(sql)
    return _count_table(store, "canada_drugs")


# ── Reactions.txt ────────────────────────────────────────────
# Col 0: REACTION_ID, 1: REPORT_ID, 2: DURATION,
# 3: DURATION_UNIT_ENG, 4: DURATION_UNIT_FR,
# 5: PT_NAME_ENG, 7: SOC_NAME_ENG, 9: MEDDRA_VERSION


def _load_reactions(store: CanadaVigilanceStore, path: Path) -> int:
    """Carrega Reactions.txt via DuckDB read_csv()."""
    src = _csv_opts(path)
    sql = f"""
        INSERT INTO canada_reactions
        SELECT
            TRY_CAST(column0 AS INTEGER),
            TRY_CAST(column1 AS INTEGER),
            TRIM(column5),
            TRIM(column7),
            TRIM(column9)
        FROM {src}
        WHERE TRY_CAST(column1 AS INTEGER) IS NOT NULL
          AND TRY_CAST(column1 AS INTEGER) > 0
    """
    store.execute_in_lock(sql)
    return _count_table(store, "canada_reactions")


# ── Drug_Product.txt / drug_products.txt ─────────────────────
# Col 0: DRUG_PRODUCT_ID, 1: DRUGNAME


def _load_products(store: CanadaVigilanceStore, path: Path) -> int:
    """Carrega Drug_Product.txt via DuckDB read_csv()."""
    src = _csv_opts(path, null_padding=True)
    sql = f"""
        INSERT INTO canada_products
        SELECT
            TRY_CAST(column0 AS INTEGER),
            TRIM(column1)
        FROM {src}
        WHERE TRY_CAST(column0 AS INTEGER) IS NOT NULL
          AND TRY_CAST(column0 AS INTEGER) > 0
    """
    store.execute_in_lock(sql)
    return _count_table(store, "canada_products")


# ── Drug_Product_Ingredients.txt ─────────────────────────────
# Col 0: LINK_ID(?), 1: DRUG_PRODUCT_ID, 2: DRUGNAME,
# 3: INGREDIENT_ID(?), 4: ACTIVE_INGREDIENT_NAME


def _load_ingredients(store: CanadaVigilanceStore, path: Path) -> int:
    """Carrega Drug_Product_Ingredients.txt via DuckDB read_csv()."""
    src = _csv_opts(path, null_padding=True)
    sql = f"""
        INSERT INTO canada_ingredients
        SELECT
            TRY_CAST(column1 AS INTEGER),
            TRIM(column4)
        FROM {src}
        WHERE TRY_CAST(column1 AS INTEGER) IS NOT NULL
          AND TRY_CAST(column1 AS INTEGER) > 0
    """
    store.execute_in_lock(sql)
    return _count_table(store, "canada_ingredients")


def _count_table(store: CanadaVigilanceStore, table: str) -> int:
    """Conta registros em uma tabela."""
    rows = store.query_in_lock(f"SELECT COUNT(*) FROM {table}")
    if rows and rows[0]:
        count = rows[0][0]
        return int(count) if isinstance(count, (int, float, str)) else 0
    return 0
