"""Tests for hypokrates.canada.downloader — auto-download Canada Vigilance."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import AsyncMock, patch


class TestDownloadCanada:
    """Tests for download_canada()."""

    async def test_skips_if_data_exists(self, tmp_path: Path) -> None:
        extract_dir = tmp_path / "extracted"
        extract_dir.mkdir()
        (extract_dir / "Reports.txt").write_text("data")

        from hypokrates.canada.downloader import download_canada

        result = await download_canada(dest_dir=tmp_path)
        assert result == extract_dir

    @patch(
        "hypokrates.canada.downloader.download_and_extract_zip",
        new_callable=AsyncMock,
    )
    async def test_calls_download(self, mock_download: AsyncMock, tmp_path: Path) -> None:
        mock_download.return_value = tmp_path / "extracted"

        from hypokrates.canada.downloader import download_canada

        await download_canada(dest_dir=tmp_path)
        mock_download.assert_called_once()
        assert "Canada Vigilance" in mock_download.call_args.kwargs.get("label", "")

    @patch(
        "hypokrates.canada.downloader.download_and_extract_zip",
        new_callable=AsyncMock,
    )
    async def test_force_redownload(self, mock_download: AsyncMock, tmp_path: Path) -> None:
        # Create existing data
        extract_dir = tmp_path / "extracted"
        extract_dir.mkdir()
        (extract_dir / "Reports.txt").write_text("old data")

        mock_download.return_value = tmp_path / "extracted"

        from hypokrates.canada.downloader import download_canada

        await download_canada(dest_dir=tmp_path, force=True)
        mock_download.assert_called_once()
