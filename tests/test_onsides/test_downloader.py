"""Tests for hypokrates.onsides.downloader — auto-download OnSIDES."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import AsyncMock, patch


class TestDownloadOnsides:
    """Tests for download_onsides()."""

    async def test_skips_if_data_exists(self, tmp_path: Path) -> None:
        extract_dir = tmp_path / "extracted"
        extract_dir.mkdir()
        (extract_dir / "product_label.csv").write_text("data")

        from hypokrates.onsides.downloader import download_onsides

        result = await download_onsides(dest_dir=tmp_path)
        assert result == extract_dir

    @patch(
        "hypokrates.onsides.downloader.download_and_extract_zip",
        new_callable=AsyncMock,
    )
    async def test_calls_download(self, mock_download: AsyncMock, tmp_path: Path) -> None:
        mock_download.return_value = tmp_path / "extracted"

        from hypokrates.onsides.downloader import download_onsides

        await download_onsides(dest_dir=tmp_path)
        mock_download.assert_called_once()
