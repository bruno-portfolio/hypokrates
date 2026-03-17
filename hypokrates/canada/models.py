"""Modelos do módulo Canada Vigilance."""

from __future__ import annotations

from pydantic import BaseModel

from hypokrates.models import MetaInfo  # noqa: TC001 — Pydantic needs at runtime
from hypokrates.stats.models import ContingencyTable  # noqa: TC001 — Pydantic needs at runtime


class CanadaBulkStatus(BaseModel):
    """Status do store Canada Vigilance."""

    loaded: bool = False
    total_reports: int = 0
    total_drugs: int = 0
    total_reactions: int = 0
    date_range: str = ""
    meta: MetaInfo


class CanadaSignalResult(BaseModel):
    """Resultado de signal para drug-event no Canada Vigilance."""

    drug: str
    event: str
    drug_event_count: int = 0
    drug_total: int = 0
    event_total: int = 0
    total_reports: int = 0
    prr: float = 0.0
    ror: float = 0.0
    ic: float = 0.0
    ebgm: float = 0.0
    signal_detected: bool = False
    table: ContingencyTable | None = None
    meta: MetaInfo
