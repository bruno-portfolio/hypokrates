"""Modelos do módulo Canada Vigilance."""

from __future__ import annotations

from pydantic import BaseModel, Field

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
    drug_event_count: int = Field(
        default=0,
        description="Reports com droga + evento no Canada Vigilance.",
    )
    drug_total: int = Field(
        default=0,
        description="Total de reports com a droga.",
    )
    event_total: int = Field(
        default=0,
        description="Total de reports com o evento.",
    )
    total_reports: int = Field(
        default=0,
        description="Total de reports no banco.",
    )
    prr: float = Field(
        default=0.0,
        description="PRR calculado no Canada Vigilance.",
    )
    ror: float = Field(
        default=0.0,
        description="ROR calculado no Canada Vigilance.",
    )
    ic: float = Field(
        default=0.0,
        description="IC (Information Component) calculado no Canada Vigilance.",
    )
    ebgm: float = Field(
        default=0.0,
        description="EBGM (GPS/DuMouchel 1999) calculado no Canada Vigilance.",
    )
    signal_detected: bool = Field(
        default=False,
        description="Heurística: >= 2 medidas significantes (PRR/ROR/IC).",
    )
    table: ContingencyTable | None = Field(
        default=None,
        description="Tabela de contingência 2x2 para cálculos adicionais.",
    )
    meta: MetaInfo
