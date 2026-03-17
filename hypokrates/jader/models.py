"""Modelos do módulo JADER."""

from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, Field

from hypokrates.models import MetaInfo  # noqa: TC001 — Pydantic needs at runtime
from hypokrates.stats.models import ContingencyTable  # noqa: TC001 — Pydantic needs at runtime


class MappingConfidence(StrEnum):
    """Nível de confiança da tradução JP→EN."""

    EXACT = "exact"
    INFERRED = "inferred"
    UNMAPPED = "unmapped"


class JADERBulkStatus(BaseModel):
    """Status do store JADER."""

    loaded: bool = False
    total_reports: int = 0
    total_drugs: int = 0
    total_reactions: int = 0
    date_range: str = ""
    exact_drug_mappings: int = 0
    inferred_drug_mappings: int = 0
    unmapped_drugs: int = 0
    exact_event_mappings: int = 0
    inferred_event_mappings: int = 0
    unmapped_events: int = 0
    meta: MetaInfo


class MappingStats(BaseModel):
    """Estatísticas de mapeamento JP→EN."""

    exact_drugs: int = 0
    inferred_drugs: int = 0
    unmapped_drugs: int = 0
    exact_events: int = 0
    inferred_events: int = 0
    unmapped_events: int = 0


class JADERSignalResult(BaseModel):
    """Resultado de signal para drug-event no JADER."""

    drug: str
    event: str
    drug_confidence: MappingConfidence = MappingConfidence.UNMAPPED
    event_confidence: MappingConfidence = MappingConfidence.UNMAPPED
    drug_event_count: int = Field(default=0)
    drug_total: int = Field(default=0)
    event_total: int = Field(default=0)
    total_reports: int = Field(default=0)
    prr: float = Field(default=0.0)
    ror: float = Field(default=0.0)
    ic: float = Field(default=0.0)
    ebgm: float = Field(default=0.0)
    signal_detected: bool = Field(default=False)
    table: ContingencyTable | None = Field(default=None)
    meta: MetaInfo
