"""Modelos para cruzamento de hipóteses FAERS + PubMed."""

from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, Field

from hypokrates.evidence.models import EvidenceBlock  # noqa: TC001 — Pydantic needs at runtime
from hypokrates.models import MetaInfo  # noqa: TC001 — Pydantic needs at runtime
from hypokrates.pubmed.models import PubMedArticle  # noqa: TC001 — Pydantic needs at runtime
from hypokrates.stats.models import SignalResult  # noqa: TC001 — Pydantic needs at runtime


class HypothesisClassification(StrEnum):
    """Classificação da hipótese baseada em sinal + literatura."""

    NOVEL_HYPOTHESIS = "novel_hypothesis"
    EMERGING_SIGNAL = "emerging_signal"
    KNOWN_ASSOCIATION = "known_association"
    NO_SIGNAL = "no_signal"


class HypothesisResult(BaseModel):
    """Resultado do cruzamento FAERS + PubMed."""

    drug: str
    event: str
    classification: HypothesisClassification
    signal: SignalResult
    literature_count: int
    articles: list[PubMedArticle] = Field(default_factory=list)
    evidence: EvidenceBlock
    summary: str
    thresholds_used: dict[str, int] = Field(default_factory=dict)
    in_label: bool | None = None
    label_detail: str | None = None
    active_trials: int | None = None
    trials_detail: str | None = None
    mechanism: str | None = None
    interactions: list[str] = Field(default_factory=list)
    enzymes: list[str] = Field(default_factory=list)
    ot_llr: float | None = None


class CompareSignalItem(BaseModel):
    """Comparação de um evento entre duas drogas."""

    event: str
    drug_prr: float
    control_prr: float
    drug_detected: bool
    control_detected: bool
    ratio: float = Field(
        description="drug_prr / control_prr. inf se control=0 e drug>0.",
    )
    stronger: str = Field(description="'drug', 'control', ou 'equal'")


class CompareResult(BaseModel):
    """Resultado da comparação de sinais entre duas drogas."""

    drug: str
    control: str
    items: list[CompareSignalItem] = Field(default_factory=list)
    drug_unique_signals: int = 0
    control_unique_signals: int = 0
    both_detected: int = 0
    total_events: int = 0
    meta: MetaInfo
