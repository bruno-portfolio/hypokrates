"""Modelos do módulo OpenTargets."""

from __future__ import annotations

from pydantic import BaseModel, Field

from hypokrates.models import MetaInfo  # noqa: TC001 — Pydantic needs at runtime


class OTAdverseEvent(BaseModel):
    """Evento adverso do OpenTargets com LRT score."""

    name: str
    count: int = 0
    log_lr: float = 0.0
    meddra_code: str | None = None


class OTDrugSafety(BaseModel):
    """Resultado de safety de uma droga no OpenTargets."""

    drug_name: str
    chembl_id: str
    adverse_events: list[OTAdverseEvent] = Field(default_factory=list)
    total_count: int = 0
    critical_value: float = 0.0
    meta: MetaInfo
