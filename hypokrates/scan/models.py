"""Modelos do módulo scan."""

from __future__ import annotations

from pydantic import BaseModel, Field

from hypokrates.cross.models import (
    HypothesisClassification,  # noqa: TC001 — Pydantic needs at runtime
)
from hypokrates.evidence.models import EvidenceBlock  # noqa: TC001 — Pydantic needs at runtime
from hypokrates.models import MetaInfo  # noqa: TC001 — Pydantic needs at runtime
from hypokrates.pubmed.models import PubMedArticle  # noqa: TC001 — Pydantic needs at runtime
from hypokrates.stats.models import SignalResult  # noqa: TC001 — Pydantic needs at runtime


class ScanItem(BaseModel):
    """Item individual do scan — resultado de uma hipótese."""

    drug: str
    event: str
    classification: HypothesisClassification
    signal: SignalResult
    literature_count: int
    articles: list[PubMedArticle] = Field(default_factory=list)
    evidence: EvidenceBlock
    summary: str
    score: float
    rank: int
    in_label: bool | None = None
    active_trials: int | None = None


class ScanResult(BaseModel):
    """Resultado completo de um scan de droga."""

    drug: str
    items: list[ScanItem] = Field(default_factory=list)
    total_scanned: int
    novel_count: int = 0
    emerging_count: int = 0
    known_count: int = 0
    no_signal_count: int = 0
    labeled_count: int = 0
    failed_count: int = 0
    skipped_events: list[str] = Field(default_factory=list)
    meta: MetaInfo
