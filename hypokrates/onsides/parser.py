"""Parser para CSVs do OnSIDES — carrega no DuckDB via read_csv."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import TYPE_CHECKING

from hypokrates.onsides.constants import (
    CSV_MEDDRA_ADVERSE_EFFECT,
    CSV_PRODUCT_ADVERSE_EFFECT,
    CSV_PRODUCT_LABEL,
    CSV_PRODUCT_TO_RXNORM,
    CSV_RXNORM_INGREDIENT,
    CSV_RXNORM_INGREDIENT_TO_PRODUCT,
    CSV_RXNORM_PRODUCT,
)

if TYPE_CHECKING:
    from hypokrates.onsides.store import OnSIDESStore

logger = logging.getLogger(__name__)

# Mapeamento: tabela DuckDB → arquivo CSV
_TABLE_CSV_MAP: list[tuple[str, str]] = [
    ("vocab_rxnorm_ingredient", CSV_RXNORM_INGREDIENT),
    ("vocab_rxnorm_product", CSV_RXNORM_PRODUCT),
    ("vocab_meddra_adverse_effect", CSV_MEDDRA_ADVERSE_EFFECT),
    ("product_label", CSV_PRODUCT_LABEL),
    ("product_to_rxnorm", CSV_PRODUCT_TO_RXNORM),
    ("vocab_rxnorm_ingredient_to_product", CSV_RXNORM_INGREDIENT_TO_PRODUCT),
    ("product_adverse_effect", CSV_PRODUCT_ADVERSE_EFFECT),
]


def load_csvs_to_store(store: OnSIDESStore, csv_dir: str) -> int:
    """Carrega todos os CSVs do OnSIDES no DuckDB store.

    Args:
        store: OnSIDESStore instance.
        csv_dir: Diretório contendo os CSVs extraídos do ZIP.

    Returns:
        Número de labels carregados.
    """
    csv_path = Path(csv_dir)

    # Limpar tabelas na ordem inversa (FK)
    for table, _ in reversed(_TABLE_CSV_MAP):
        store.execute_in_lock(f"DELETE FROM {table}")
        logger.debug("Cleared table %s", table)

    total_labels = 0
    for table, csv_name in _TABLE_CSV_MAP:
        file_path = csv_path / csv_name
        if not file_path.exists():
            logger.warning("OnSIDES CSV not found: %s", file_path)
            continue

        # DuckDB read_csv com forward slashes (cross-platform)
        csv_str = str(file_path).replace("\\", "/")
        count = store.read_csv_in_lock(table, csv_str)
        logger.info("Loaded %s: %d rows from %s", table, count, csv_name)

        if table == "product_label":
            total_labels = count

    logger.info("OnSIDES load complete: %d labels", total_labels)
    return total_labels
