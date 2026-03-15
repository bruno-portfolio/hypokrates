"""Testes do downloader ANVISA."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from hypokrates.anvisa.downloader import needs_refresh


class TestNeedsRefresh:
    def test_none_needs_refresh(self) -> None:
        assert needs_refresh(None) is True

    def test_recent_no_refresh(self) -> None:
        recent = datetime.now(UTC).isoformat()
        assert needs_refresh(recent) is False

    def test_old_needs_refresh(self) -> None:
        old = (datetime.now(UTC) - timedelta(days=31)).isoformat()
        assert needs_refresh(old) is True

    def test_exactly_30_needs_refresh(self) -> None:
        exactly_30 = (datetime.now(UTC) - timedelta(days=30)).isoformat()
        assert needs_refresh(exactly_30) is True

    def test_29_days_no_refresh(self) -> None:
        day29 = (datetime.now(UTC) - timedelta(days=29)).isoformat()
        assert needs_refresh(day29) is False

    def test_invalid_format(self) -> None:
        assert needs_refresh("not-a-date") is True

    def test_empty_string(self) -> None:
        assert needs_refresh("") is True
