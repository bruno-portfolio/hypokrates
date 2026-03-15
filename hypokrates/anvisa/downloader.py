"""Download automatico do CSV de medicamentos da ANVISA."""

from __future__ import annotations

import logging
from datetime import UTC, datetime
from typing import TYPE_CHECKING

from hypokrates.anvisa.constants import ANVISA_MEDICAMENTOS_URL, ANVISA_REFRESH_DAYS

if TYPE_CHECKING:
    from collections.abc import Callable
    from pathlib import Path

logger = logging.getLogger(__name__)


async def download_medicamentos(
    *,
    dest_dir: Path | None = None,
    force: bool = False,
    on_progress: Callable[[int, int], None] | None = None,
) -> Path:
    """Baixa CSV de medicamentos da ANVISA.

    Idempotente: pula se arquivo existe e nao foi forcado.

    Args:
        dest_dir: Diretorio de destino (default: ~/.cache/hypokrates/anvisa/).
        force: Forcar re-download mesmo se arquivo existe.
        on_progress: Callback opcional (bytes_downloaded, total_bytes).

    Returns:
        Caminho do arquivo CSV baixado.
    """
    import httpx

    if dest_dir is None:
        from hypokrates.config import get_config

        dest_dir = get_config().cache_dir / "anvisa"

    dest_dir.mkdir(parents=True, exist_ok=True)
    csv_path = dest_dir / "TA_CONSULTA_MEDICAMENTOS.CSV"

    if csv_path.exists() and not force:
        logger.info("ANVISA CSV already exists: %s", csv_path)
        return csv_path

    logger.info("Downloading ANVISA medicamentos CSV from %s", ANVISA_MEDICAMENTOS_URL)

    async with (
        httpx.AsyncClient(
            timeout=120.0,
            follow_redirects=True,
            verify=False,
        ) as client,
        client.stream(
            "GET",
            ANVISA_MEDICAMENTOS_URL,
            headers={"User-Agent": "Mozilla/5.0"},
        ) as response,
    ):
        response.raise_for_status()
        total = int(response.headers.get("content-length", 0))
        downloaded = 0

        with csv_path.open("wb") as f:
            async for chunk in response.aiter_bytes(chunk_size=65536):
                f.write(chunk)
                downloaded += len(chunk)
                if on_progress is not None:
                    on_progress(downloaded, total)

    logger.info("Downloaded ANVISA CSV: %s (%.1f MB)", csv_path, downloaded / 1e6)
    return csv_path


def needs_refresh(store_loaded_at: str | None) -> bool:
    """Verifica se os dados precisam de refresh (>30 dias)."""
    if store_loaded_at is None:
        return True
    try:
        loaded = datetime.fromisoformat(store_loaded_at)
        age_days = (datetime.now(UTC) - loaded).days
        return age_days >= ANVISA_REFRESH_DAYS
    except (ValueError, TypeError):
        return True
