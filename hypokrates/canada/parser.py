"""Parser para arquivos $-delimited do Canada Vigilance."""

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
    from hypokrates.canada.store import CanadaVigilanceStore

logger = logging.getLogger(__name__)

# Batch size para inserts
_BATCH_SIZE = 5000


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
    reports_path = base_path / FILE_REPORTS
    if reports_path.exists():
        total_reports = _load_reports(store, reports_path)
        logger.info("Canada: loaded %d reports", total_reports)

    # 2. Report_Drug
    drugs_path = base_path / FILE_REPORT_DRUG
    if drugs_path.exists():
        count = _load_report_drugs(store, drugs_path)
        logger.info("Canada: loaded %d drug records", count)

    # 3. Reactions
    reactions_path = base_path / FILE_REACTIONS
    if reactions_path.exists():
        count = _load_reactions(store, reactions_path)
        logger.info("Canada: loaded %d reaction records", count)

    # 4. Drug_Product
    products_path = base_path / FILE_DRUG_PRODUCT
    if products_path.exists():
        count = _load_products(store, products_path)
        logger.info("Canada: loaded %d products", count)

    # 5. Drug_Product_Ingredients
    ingredients_path = base_path / FILE_DRUG_INGREDIENTS
    if ingredients_path.exists():
        count = _load_ingredients(store, ingredients_path)
        logger.info("Canada: loaded %d ingredients", count)

    logger.info("Canada Vigilance load complete: %d reports", total_reports)
    return total_reports


def _read_delimited(path: Path) -> csv.DictReader[str]:
    """Lê arquivo $-delimited como DictReader."""
    # Canada Vigilance usa $ como delimitador e " como quotechar
    fh = path.open(encoding="utf-8", errors="replace")
    return csv.DictReader(fh, delimiter=DELIMITER, quotechar='"')


def _safe_int(val: str | None, default: int = 0) -> int:
    """Converte string para int com fallback."""
    if not val or not val.strip():
        return default
    try:
        return int(val.strip())
    except ValueError:
        return default


def _load_reports(store: CanadaVigilanceStore, path: Path) -> int:
    """Carrega Reports.txt."""
    reader = _read_delimited(path)
    rows: list[list[object]] = []
    count = 0

    for record in reader:
        report_id = _safe_int(record.get("REPORT_ID"))
        if report_id == 0:
            continue
        rows.append(
            [
                report_id,
                (record.get("DATRECEIVED") or "").strip(),
                (record.get("GENDER_CODE") or "").strip(),
                (record.get("AGE") or "").strip(),
                (record.get("OUTCOME_CODE") or "").strip(),
                (record.get("SERIOUSNESS_CODE") or "").strip(),
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


def _load_report_drugs(store: CanadaVigilanceStore, path: Path) -> int:
    """Carrega Report_Drug.txt."""
    reader = _read_delimited(path)
    rows: list[list[object]] = []
    count = 0

    for record in reader:
        report_id = _safe_int(record.get("REPORT_ID"))
        if report_id == 0:
            continue
        rows.append(
            [
                _safe_int(record.get("REPORT_DRUG_ID")),
                report_id,
                _safe_int(record.get("DRUG_PRODUCT_ID")),
                (record.get("DRUGINVOLV_ENG") or "").strip(),
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


def _load_reactions(store: CanadaVigilanceStore, path: Path) -> int:
    """Carrega Reactions.txt."""
    reader = _read_delimited(path)
    rows: list[list[object]] = []
    count = 0

    for record in reader:
        report_id = _safe_int(record.get("REPORT_ID"))
        if report_id == 0:
            continue
        rows.append(
            [
                _safe_int(record.get("REACTION_ID")),
                report_id,
                (record.get("PT_NAME_ENG") or "").strip(),
                (record.get("SOC_NAME_ENG") or "").strip(),
                (record.get("MEDDRA_VERSION") or "").strip(),
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


def _load_products(store: CanadaVigilanceStore, path: Path) -> int:
    """Carrega Drug_Product.txt."""
    reader = _read_delimited(path)
    rows: list[list[object]] = []
    count = 0

    for record in reader:
        product_id = _safe_int(record.get("DRUG_PRODUCT_ID"))
        if product_id == 0:
            continue
        rows.append(
            [
                product_id,
                (record.get("DRUGNAME") or "").strip(),
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


def _load_ingredients(store: CanadaVigilanceStore, path: Path) -> int:
    """Carrega Drug_Product_Ingredients.txt."""
    reader = _read_delimited(path)
    rows: list[list[object]] = []
    count = 0

    for record in reader:
        product_id = _safe_int(record.get("DRUG_PRODUCT_ID"))
        if product_id == 0:
            continue
        rows.append(
            [
                product_id,
                (record.get("ACTIVE_INGREDIENT_NAME") or "").strip(),
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
