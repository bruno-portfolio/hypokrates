"""Auto-download of Canada Vigilance bulk data from Health Canada."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from hypokrates.canada.constants import CANADA_BULK_URL
from hypokrates.download.base import download_and_extract_zip

if TYPE_CHECKING:
    from collections.abc import Callable
    from pathlib import Path

logger = logging.getLogger(__name__)


async def download_canada(
    *,
    dest_dir: Path | None = None,
    force: bool = False,
    on_progress: Callable[[int, int], None] | None = None,
) -> Path:
    """Download and extract Canada Vigilance bulk data.

    Idempotent: skips if data already exists and not forced.

    Args:
        dest_dir: Destination directory (default: ~/.cache/hypokrates/canada/).
        force: Force re-download even if data exists.
        on_progress: Optional callback (bytes_downloaded, total_bytes).

    Returns:
        Path to the directory containing extracted CSV files.
    """
    if dest_dir is None:
        from hypokrates.config import get_config

        dest_dir = get_config().cache_dir / "canada"

    dest_dir.mkdir(parents=True, exist_ok=True)
    extract_dir = dest_dir / "extracted"

    if extract_dir.exists() and not force:
        # Check if extraction directory has files
        files = list(extract_dir.rglob("*.txt"))
        if files:
            logger.info("Canada Vigilance data already exists: %s", extract_dir)
            return extract_dir

    if force:
        from hypokrates.download.base import cleanup_extract_dir

        cleanup_extract_dir(dest_dir)

    logger.info("Downloading Canada Vigilance bulk data (~325MB, one-time setup)...")
    return await download_and_extract_zip(
        CANADA_BULK_URL,
        dest_dir,
        label="Canada Vigilance",
        on_progress=on_progress,
    )
