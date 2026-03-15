"""Orquestrador de carga de FAERS quarterly ZIPs.

Carrega todos os ZIPs de um diretório ou incrementalmente (apenas novos).
"""

from __future__ import annotations

import asyncio
import logging
from pathlib import Path
from typing import TYPE_CHECKING

from hypokrates.faers_bulk.store import FAERSBulkStore

if TYPE_CHECKING:
    from collections.abc import Callable

logger = logging.getLogger(__name__)


async def load_all_quarters(
    zip_dir: str | Path,
    *,
    on_progress: Callable[[int, int, str], None] | None = None,
) -> int:
    """Carrega todos os ZIPs FAERS de um diretório.

    Args:
        zip_dir: Diretório contendo os ZIPs FAERS.
        on_progress: Callback opcional (completed, total, quarter_key).

    Returns:
        Número total de demo rows carregadas.
    """
    zip_dir_path = Path(zip_dir)
    zips = sorted(zip_dir_path.glob("faers_ascii_*.zip"))

    if not zips:
        logger.warning("No FAERS ZIPs found in %s", zip_dir_path)
        return 0

    store = FAERSBulkStore.get_instance()
    total_loaded = 0
    total = len(zips)

    for i, zip_path in enumerate(zips):
        quarter_key = zip_path.stem.replace("faers_ascii_", "").upper()
        try:
            count = await asyncio.to_thread(store.load_quarter, zip_path)
            total_loaded += count
            logger.info(
                "Loaded %d/%d: %s (%d rows)",
                i + 1,
                total,
                quarter_key,
                count,
            )
        except Exception:
            logger.warning("Failed to load %s, skipping", zip_path.name)
            count = 0

        if on_progress is not None:
            on_progress(i + 1, total, quarter_key)

    logger.info("Load complete: %d total demo rows from %d ZIPs", total_loaded, total)
    return total_loaded


async def load_incremental(
    zip_dir: str | Path,
    *,
    on_progress: Callable[[int, int, str], None] | None = None,
) -> int:
    """Carrega apenas ZIPs ainda não carregados.

    Args:
        zip_dir: Diretório contendo os ZIPs FAERS.
        on_progress: Callback opcional (completed, total, quarter_key).

    Returns:
        Número de demo rows carregadas (novos apenas).
    """
    zip_dir_path = Path(zip_dir)
    zips = sorted(zip_dir_path.glob("faers_ascii_*.zip"))

    if not zips:
        logger.warning("No FAERS ZIPs found in %s", zip_dir_path)
        return 0

    store = FAERSBulkStore.get_instance()
    loaded_quarters = await asyncio.to_thread(store.get_loaded_quarters)
    loaded_keys = {q.quarter_key for q in loaded_quarters}

    new_zips = [z for z in zips if _extract_key(z) not in loaded_keys]

    if not new_zips:
        logger.info("All quarters already loaded")
        return 0

    total_loaded = 0
    total = len(new_zips)

    for i, zip_path in enumerate(new_zips):
        quarter_key = _extract_key(zip_path)
        try:
            count = await asyncio.to_thread(store.load_quarter, zip_path)
            total_loaded += count
        except Exception:
            logger.warning("Failed to load %s, skipping", zip_path.name)
            count = 0

        if on_progress is not None:
            on_progress(i + 1, total, quarter_key)

    logger.info(
        "Incremental load: %d demo rows from %d new ZIPs",
        total_loaded,
        total,
    )
    return total_loaded


def _extract_key(zip_path: Path) -> str:
    """Extrai quarter key de um path (e.g., '2024Q3')."""
    import re

    match = re.search(r"(\d{4})[qQ](\d)", zip_path.name)
    if match:
        return f"{match.group(1)}Q{match.group(2)}"
    return zip_path.stem
