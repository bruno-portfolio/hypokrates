"""Download de FAERS quarterly ASCII ZIPs da FDA.

Suporta download individual ou incremental (quarters faltantes).
"""

from __future__ import annotations

import asyncio
import logging
from datetime import UTC, datetime
from pathlib import Path
from typing import TYPE_CHECKING

from hypokrates.faers_bulk.constants import MIN_YEAR

if TYPE_CHECKING:
    from collections.abc import Callable

logger = logging.getLogger(__name__)

# URL base para quarterly exports (FAERS ASCII)
_FDA_BULK_BASE_URL = "https://fis.fda.gov/content/Exports"


def _quarter_url(year: int, quarter: int) -> str:
    """Constrói URL de download para um quarter."""
    return f"{_FDA_BULK_BASE_URL}/faers_ascii_{year}Q{quarter}.zip"


def _quarter_filename(year: int, quarter: int) -> str:
    """Nome do arquivo ZIP para um quarter."""
    return f"faers_ascii_{year}Q{quarter}.zip"


def list_available_quarters(*, min_year: int = MIN_YEAR) -> list[tuple[int, int]]:
    """Lista quarters disponíveis baseado na data atual.

    FAERS publica com ~3 meses de atraso. Estimamos quarters
    disponíveis até 2 quarters antes do atual.

    Args:
        min_year: Ano mínimo (default 2014, início do formato FAERS).

    Returns:
        Lista de tuplas (year, quarter) em ordem cronológica.
    """
    now = datetime.now(UTC)
    current_year = now.year
    current_month = now.month
    current_quarter = (current_month - 1) // 3 + 1

    # FDA publica com ~3 meses de atraso → último disponível é 2 quarters atrás
    available_up_to_year = current_year
    available_up_to_quarter = current_quarter - 2
    if available_up_to_quarter <= 0:
        available_up_to_quarter += 4
        available_up_to_year -= 1

    quarters: list[tuple[int, int]] = []
    for year in range(min_year, available_up_to_year + 1):
        for q in range(1, 5):
            if year == available_up_to_year and q > available_up_to_quarter:
                break
            quarters.append((year, q))

    return quarters


async def download_quarter(
    year: int,
    quarter: int,
    *,
    dest_dir: str | Path,
    on_progress: Callable[[int, int], None] | None = None,
) -> Path:
    """Baixa um quarter FAERS ASCII ZIP via httpx streaming.

    Args:
        year: Ano (e.g., 2024).
        quarter: Quarter (1-4).
        dest_dir: Diretório de destino.
        on_progress: Callback opcional (bytes_downloaded, total_bytes).

    Returns:
        Caminho do arquivo ZIP baixado.

    Raises:
        httpx.HTTPStatusError: Se o download falhar.
    """
    import httpx

    dest_path = Path(dest_dir)
    dest_path.mkdir(parents=True, exist_ok=True)
    zip_path = dest_path / _quarter_filename(year, quarter)

    if zip_path.exists():
        logger.info("Quarter %dQ%d already downloaded: %s", year, quarter, zip_path)
        return zip_path

    url = _quarter_url(year, quarter)
    logger.info("Downloading %dQ%d from %s", year, quarter, url)

    async with (
        httpx.AsyncClient(timeout=600.0, follow_redirects=True) as client,
        client.stream("GET", url) as response,
    ):
        response.raise_for_status()
        total = int(response.headers.get("content-length", 0))
        downloaded = 0

        with zip_path.open("wb") as f:
            async for chunk in response.aiter_bytes(chunk_size=65536):
                f.write(chunk)
                downloaded += len(chunk)
                if on_progress is not None:
                    on_progress(downloaded, total)

    logger.info("Downloaded %dQ%d: %s (%.1f MB)", year, quarter, zip_path, downloaded / 1e6)
    return zip_path


async def download_latest(
    *,
    dest_dir: str | Path,
    on_progress: Callable[[int, int], None] | None = None,
) -> list[Path]:
    """Baixa quarters que ainda não estão no store.

    Compara quarters disponíveis com quarters carregados e baixa os faltantes.

    Args:
        dest_dir: Diretório de destino para os ZIPs.
        on_progress: Callback opcional (bytes_downloaded, total_bytes).

    Returns:
        Lista de caminhos dos ZIPs baixados.
    """
    from hypokrates.faers_bulk.store import FAERSBulkStore

    store = FAERSBulkStore.get_instance()
    loaded = await asyncio.to_thread(store.get_loaded_quarters)
    loaded_keys = {q.quarter_key for q in loaded}

    available = list_available_quarters()
    missing = [(y, q) for y, q in available if f"{y}Q{q}" not in loaded_keys]

    if not missing:
        logger.info("All available quarters already downloaded/loaded")
        return []

    logger.info("Downloading %d missing quarters", len(missing))
    paths: list[Path] = []
    for year, quarter in missing:
        try:
            path = await download_quarter(
                year, quarter, dest_dir=dest_dir, on_progress=on_progress
            )
            paths.append(path)
        except Exception:
            logger.warning("Failed to download %dQ%d, skipping", year, quarter)

    return paths
