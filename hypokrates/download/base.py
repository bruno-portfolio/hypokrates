"""Shared download utilities — streaming download, ZIP extraction, freshness check."""

from __future__ import annotations

import asyncio
import logging
import shutil
import zipfile
from datetime import UTC, datetime
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Callable
    from pathlib import Path

logger = logging.getLogger(__name__)


async def download_file(
    url: str,
    dest_path: Path,
    *,
    label: str = "",
    timeout: float = 600.0,
    on_progress: Callable[[int, int], None] | None = None,
    headers: dict[str, str] | None = None,
) -> Path:
    """Download a file via httpx streaming with atomic write.

    Downloads to a `.tmp` file first, then renames on success.
    Idempotent: skips if dest_path already exists.

    Args:
        url: URL to download from.
        dest_path: Final file path.
        label: Human-readable label for logging (e.g., "Canada Vigilance").
        timeout: Request timeout in seconds.
        on_progress: Optional callback (bytes_downloaded, total_bytes).
        headers: Optional HTTP headers.

    Returns:
        Path to the downloaded file.
    """
    if dest_path.exists():
        logger.info("%s already downloaded: %s", label or "File", dest_path)
        return dest_path

    import httpx

    dest_path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = dest_path.with_suffix(dest_path.suffix + ".tmp")

    log_label = label or dest_path.name
    logger.info("Downloading %s from %s", log_label, url)

    req_headers = {"User-Agent": "Mozilla/5.0"}
    if headers:
        req_headers.update(headers)

    try:
        async with (
            httpx.AsyncClient(
                timeout=timeout,
                follow_redirects=True,
            ) as client,
            client.stream("GET", url, headers=req_headers) as response,
        ):
            response.raise_for_status()
            total = int(response.headers.get("content-length", 0))
            downloaded = 0

            with tmp_path.open("wb") as f:
                async for chunk in response.aiter_bytes(chunk_size=65536):
                    f.write(chunk)
                    downloaded += len(chunk)
                    if on_progress is not None:
                        on_progress(downloaded, total)

        # Atomic rename
        tmp_path.rename(dest_path)
        logger.info("Downloaded %s: %s (%.1f MB)", log_label, dest_path, downloaded / 1e6)
    except Exception:
        # Clean up partial download
        if tmp_path.exists():
            tmp_path.unlink()
        raise

    return dest_path


def extract_zip(
    zip_path: Path,
    dest_dir: Path,
    *,
    label: str = "",
) -> Path:
    """Extract a ZIP file to a destination directory.

    Args:
        zip_path: Path to the ZIP file.
        dest_dir: Directory to extract into.
        label: Human-readable label for logging.

    Returns:
        Path to the extraction directory.

    Raises:
        zipfile.BadZipFile: If the ZIP is corrupted.
    """
    dest_dir.mkdir(parents=True, exist_ok=True)
    log_label = label or zip_path.name

    logger.info("Extracting %s to %s", log_label, dest_dir)

    try:
        with zipfile.ZipFile(zip_path, "r") as zf:
            # Security: validate no path traversal in ZIP entries
            for member in zf.infolist():
                member_path = (dest_dir / member.filename).resolve()
                if not str(member_path).startswith(str(dest_dir.resolve())):
                    msg = f"Path traversal detected in ZIP: {member.filename}"
                    raise zipfile.BadZipFile(msg)
            zf.extractall(dest_dir)
            file_count = len(zf.namelist())
    except zipfile.BadZipFile:
        logger.error("Corrupted ZIP file: %s — deleting", zip_path)
        zip_path.unlink(missing_ok=True)
        raise

    logger.info("Extracted %s: %d files in %s", log_label, file_count, dest_dir)
    return dest_dir


async def download_and_extract_zip(
    url: str,
    dest_dir: Path,
    *,
    label: str = "",
    timeout: float = 600.0,
    on_progress: Callable[[int, int], None] | None = None,
    headers: dict[str, str] | None = None,
    keep_zip: bool = False,
) -> Path:
    """Download a ZIP file and extract it.

    Args:
        url: URL to download from.
        dest_dir: Directory to store the ZIP and extract into.
        label: Human-readable label for logging.
        timeout: Request timeout in seconds.
        on_progress: Optional callback (bytes_downloaded, total_bytes).
        headers: Optional HTTP headers.
        keep_zip: If True, keep the ZIP after extraction. Default: delete it.

    Returns:
        Path to the extraction directory.
    """
    zip_name = url.rsplit("/", 1)[-1] if "/" in url else "download.zip"
    zip_path = dest_dir / zip_name

    await download_file(
        url,
        zip_path,
        label=label,
        timeout=timeout,
        on_progress=on_progress,
        headers=headers,
    )

    extract_dir = dest_dir / "extracted"
    await asyncio.to_thread(extract_zip, zip_path, extract_dir, label=label)

    if not keep_zip:
        zip_path.unlink(missing_ok=True)

    return extract_dir


def needs_refresh(loaded_at_iso: str | None, *, max_age_days: int) -> bool:
    """Check if data needs refresh based on loaded_at timestamp.

    Args:
        loaded_at_iso: ISO format datetime string of last load, or None.
        max_age_days: Maximum age in days before refresh is needed.

    Returns:
        True if data should be re-downloaded.
    """
    if loaded_at_iso is None:
        return True
    try:
        loaded = datetime.fromisoformat(loaded_at_iso)
        age_days = (datetime.now(UTC) - loaded).days
        return age_days >= max_age_days
    except (ValueError, TypeError):
        return True


def cleanup_extract_dir(dest_dir: Path) -> None:
    """Remove extraction directory for a clean re-download."""
    extract_dir = dest_dir / "extracted"
    if extract_dir.exists():
        shutil.rmtree(extract_dir)
