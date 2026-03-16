"""Modelos de evidência com proveniência."""

from __future__ import annotations

from datetime import datetime  # noqa: TC003 — Pydantic needs at runtime
from enum import StrEnum

from pydantic import BaseModel, Field


class Limitation(StrEnum):
    """Limitações conhecidas de fontes de dados."""

    VOLUNTARY_REPORTING = "voluntary_reporting"
    NO_DENOMINATOR = "no_denominator"
    DUPLICATE_REPORTS = "duplicate_reports"
    MISSING_DATA = "missing_data"
    INDICATION_BIAS = "indication_bias"
    NOTORIETY_BIAS = "notoriety_bias"
    NO_CAUSATION = "no_causation"
    CO_ADMINISTRATION = "co_administration"


class EvidenceBlock(BaseModel):
    """Bloco de evidência com proveniência completa."""

    source: str = Field(description="Fonte de dados (e.g., 'OpenFDA/FAERS')")
    source_version: str | None = None
    query: dict[str, str | int | float | bool | None] = Field(default_factory=dict)
    retrieved_at: datetime
    cached: bool = False
    data: dict[str, object] = Field(default_factory=dict)
    limitations: list[Limitation] = Field(default_factory=list)
    disclaimer: str = ""
    methodology: str | None = None
    confidence: str | None = None
