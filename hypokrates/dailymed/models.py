"""Modelos do módulo DailyMed."""

from __future__ import annotations

from pydantic import BaseModel, Field

from hypokrates.models import MetaInfo  # noqa: TC001 — Pydantic needs at runtime


class LabelEventsResult(BaseModel):
    """Resultado de extração de eventos adversos de uma bula."""

    drug: str
    set_id: str | None = None
    events: list[str] = Field(default_factory=list)
    raw_text: str = ""
    indications_text: str = ""
    meta: MetaInfo


class LabelCheckResult(BaseModel):
    """Resultado da verificação se um evento está na bula."""

    drug: str
    event: str
    in_label: bool = False
    matched_terms: list[str] = Field(default_factory=list)
    set_id: str | None = None
    meta: MetaInfo
