"""Tests for hypokrates.download.base — shared download utilities."""

from __future__ import annotations

import zipfile
from pathlib import Path

import pytest

from hypokrates.download.base import (
    cleanup_extract_dir,
    extract_zip,
    needs_refresh,
)


class TestNeedsRefresh:
    """Tests for freshness check."""

    def test_none_needs_refresh(self) -> None:
        assert needs_refresh(None, max_age_days=30) is True

    def test_invalid_string_needs_refresh(self) -> None:
        assert needs_refresh("not-a-date", max_age_days=30) is True

    def test_recent_no_refresh(self) -> None:
        from datetime import UTC, datetime

        now_iso = datetime.now(UTC).isoformat()
        assert needs_refresh(now_iso, max_age_days=30) is False

    def test_old_needs_refresh(self) -> None:
        from datetime import UTC, datetime, timedelta

        old = (datetime.now(UTC) - timedelta(days=31)).isoformat()
        assert needs_refresh(old, max_age_days=30) is True

    def test_exactly_at_boundary(self) -> None:
        from datetime import UTC, datetime, timedelta

        boundary = (datetime.now(UTC) - timedelta(days=30)).isoformat()
        assert needs_refresh(boundary, max_age_days=30) is True


class TestExtractZip:
    """Tests for ZIP extraction."""

    def test_extract_valid_zip(self, tmp_path: Path) -> None:
        # Create a test ZIP
        zip_path = tmp_path / "test.zip"
        with zipfile.ZipFile(zip_path, "w") as zf:
            zf.writestr("file1.txt", "hello")
            zf.writestr("file2.csv", "a,b,c")

        dest = tmp_path / "output"
        result = extract_zip(zip_path, dest, label="test")

        assert result == dest
        assert (dest / "file1.txt").exists()
        assert (dest / "file2.csv").exists()

    def test_extract_bad_zip_deletes(self, tmp_path: Path) -> None:
        zip_path = tmp_path / "bad.zip"
        zip_path.write_text("not a zip file")

        dest = tmp_path / "output"
        with pytest.raises(zipfile.BadZipFile):
            extract_zip(zip_path, dest)

        # Bad ZIP should be deleted
        assert not zip_path.exists()


class TestCleanupExtractDir:
    """Tests for cleanup."""

    def test_cleanup_existing(self, tmp_path: Path) -> None:
        extract = tmp_path / "extracted"
        extract.mkdir()
        (extract / "file.txt").write_text("data")

        cleanup_extract_dir(tmp_path)
        assert not extract.exists()

    def test_cleanup_nonexistent(self, tmp_path: Path) -> None:
        # Should not raise
        cleanup_extract_dir(tmp_path)


class TestDownloadFile:
    """Tests for download_file (mocked HTTP)."""

    async def test_skips_if_exists(self, tmp_path: Path) -> None:
        dest = tmp_path / "existing.zip"
        dest.write_text("already here")

        from hypokrates.download.base import download_file

        result = await download_file("https://example.com/file.zip", dest)
        assert result == dest
        # File content unchanged (no download happened)
        assert dest.read_text() == "already here"

    async def test_verify_false_forwarded(self, tmp_path: Path) -> None:
        """verify=False is forwarded to httpx.AsyncClient."""
        import contextlib
        from unittest.mock import patch

        import httpx

        from hypokrates.download.base import download_file

        dest = tmp_path / "test.csv"
        captured: dict[str, object] = {}

        def spy_init(self_inner: object, **kwargs: object) -> None:
            captured.update(kwargs)
            raise ConnectionError("spy")

        with (
            patch.object(httpx.AsyncClient, "__init__", spy_init),
            contextlib.suppress(ConnectionError),
        ):
            await download_file(
                "https://example.com/f.csv",
                dest,
                verify=False,
            )

        assert captured.get("verify") is False
