"""Modelos do módulo ClinicalTrials.gov."""

from __future__ import annotations

from pydantic import BaseModel, Field

from hypokrates.models import MetaInfo  # noqa: TC001 — Pydantic needs at runtime


class ClinicalTrial(BaseModel):
    """Representação simplificada de um trial clínico."""

    nct_id: str
    title: str = ""
    status: str = ""
    phase: str = ""
    start_date: str | None = None
    conditions: list[str] = Field(default_factory=list)
    interventions: list[str] = Field(default_factory=list)


class TrialsResult(BaseModel):
    """Resultado de busca de trials clínicos."""

    drug: str
    event: str
    total_count: int = 0
    active_count: int = 0
    trials: list[ClinicalTrial] = Field(default_factory=list)
    meta: MetaInfo
