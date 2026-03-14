"""Testes para hypokrates.utils.time — utilitários de tempo."""

from __future__ import annotations

from datetime import UTC, datetime

from hypokrates.utils.time import utcnow


class TestUtcNow:
    """utcnow retorna datetime timezone-aware."""

    def test_returns_utc_aware(self) -> None:
        now = utcnow()
        assert isinstance(now, datetime)
        assert now.tzinfo is not None

    def test_is_close_to_current_time(self) -> None:
        before = datetime.now(UTC)
        now = utcnow()
        after = datetime.now(UTC)
        assert before <= now <= after
