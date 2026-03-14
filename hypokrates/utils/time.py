"""Utilitários de tempo."""

from __future__ import annotations

from datetime import UTC, datetime


def utcnow() -> datetime:
    """Retorna datetime UTC aware (timezone-aware)."""
    return datetime.now(UTC)
