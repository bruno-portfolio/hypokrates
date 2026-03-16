"""Modelos do módulo OnSIDES."""

from __future__ import annotations

from pydantic import BaseModel, Field

from hypokrates.models import MetaInfo  # noqa: TC001 — Pydantic needs at runtime


class OnSIDESEvent(BaseModel):
    """Evento adverso extraído de bulas via OnSIDES (PubMedBERT NLP)."""

    meddra_id: int
    meddra_name: str
    label_section: str = Field(
        description="Label section: BW (Boxed Warning), WP (Warnings/Precautions), "
        "AR (Adverse Reactions).",
    )
    confidence: float = Field(
        description="Prediction confidence (pred1, 0-1) from PubMedBERT model.",
    )
    sources: list[str] = Field(
        default_factory=list,
        description="Countries where this ADE was found in labels (US, EU, UK, JP).",
    )
    num_sources: int = Field(
        default=0,
        description="Number of countries with this ADE in labels.",
    )


class OnSIDESResult(BaseModel):
    """Resultado da busca OnSIDES para uma droga."""

    drug_name: str
    events: list[OnSIDESEvent] = Field(default_factory=list)
    total_events: int = 0
    meta: MetaInfo
