"""Auto-download of OnSIDES data from GitHub releases."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from hypokrates.download.base import download_and_extract_zip
from hypokrates.onsides.constants import CSV_PRODUCT_LABEL

if TYPE_CHECKING:
    from collections.abc import Callable
    from pathlib import Path

logger = logging.getLogger(__name__)

# OnSIDES v3.1.0 from tatonetti-lab GitHub releases
ONSIDES_DOWNLOAD_URL = (
    "https://github.com/tatonetti-lab/onsides/releases/download/v3.1.0/onsides-v3.1.0.zip"
)


async def download_onsides(
    *,
    dest_dir: Path | None = None,
    force: bool = False,
    on_progress: Callable[[int, int], None] | None = None,
) -> Path:
    """Download and extract OnSIDES data.

    Idempotent: skips if data already exists and not forced.

    Args:
        dest_dir: Destination directory (default: ~/.cache/hypokrates/onsides/).
        force: Force re-download even if data exists.
        on_progress: Optional callback (bytes_downloaded, total_bytes).

    Returns:
        Path to the directory containing extracted CSV files.
    """
    if dest_dir is None:
        from hypokrates.config import get_config

        dest_dir = get_config().cache_dir / "onsides"

    dest_dir.mkdir(parents=True, exist_ok=True)
    extract_dir = dest_dir / "extracted"

    if extract_dir.exists() and not force:
        # Look for known OnSIDES file to find the csv/ subdirectory
        matches = list(extract_dir.rglob(CSV_PRODUCT_LABEL))
        if matches:
            logger.info("OnSIDES data already exists: %s", extract_dir)
            return matches[0].parent

    if force:
        from hypokrates.download.base import cleanup_extract_dir

        cleanup_extract_dir(dest_dir)

    logger.info("Downloading OnSIDES data (~313MB, one-time setup)...")
    extract_path = await download_and_extract_zip(
        ONSIDES_DOWNLOAD_URL,
        dest_dir,
        label="OnSIDES",
        on_progress=on_progress,
    )

    # OnSIDES ZIP has csv/ subdirectory — find known file
    matches = list(extract_path.rglob(CSV_PRODUCT_LABEL))
    if matches:
        return matches[0].parent

    return extract_path
