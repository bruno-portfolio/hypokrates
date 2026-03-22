"""Modelos para cruzamento de hipóteses FAERS + PubMed."""

from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, Field

from hypokrates.evidence.models import EvidenceBlock  # noqa: TC001 — Pydantic needs at runtime
from hypokrates.faers.models import CoSuspectProfile  # noqa: TC001 — Pydantic needs at runtime
from hypokrates.models import MetaInfo  # noqa: TC001 — Pydantic needs at runtime
from hypokrates.pubmed.models import PubMedArticle  # noqa: TC001 — Pydantic needs at runtime
from hypokrates.stats.models import SignalResult  # noqa: TC001 — Pydantic needs at runtime


class HypothesisClassification(StrEnum):
    """Classificação da hipótese baseada em sinal + literatura."""

    NOVEL_HYPOTHESIS = "novel_hypothesis"
    EMERGING_SIGNAL = "emerging_signal"
    KNOWN_ASSOCIATION = "known_association"
    NO_SIGNAL = "no_signal"
    PROTECTIVE_SIGNAL = "protective_signal"


class CoSignalItem(BaseModel):
    """Sinal de uma co-drug para o mesmo evento."""

    drug: str
    prr: float
    signal_detected: bool


class CoAdminAnalysis(BaseModel):
    """Resultado da análise de confounding por co-administração.

    Combina Layer 1 (co-suspect profile) com Layer 2 (overlap + PRR comparativo)
    para determinar se o sinal é específico da droga ou artefato de co-administração.
    """

    profile: CoSuspectProfile
    overlap_ratio: float = 0.0
    specificity_ratio: float | None = None
    is_specific: bool = True
    co_signals: list[CoSignalItem] = Field(default_factory=list)
    verdict: str = "inconclusive"


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
    coadmin: CoAdminAnalysis | None = None
    indication_confounding: bool = False
    onsides_sources: list[str] | None = None
    pharmacogenomics: list[str] = Field(default_factory=list)
    canada_reports: int | None = None
    canada_signal: bool | None = None
    jader_reports: int | None = None
    jader_signal: bool | None = None


class StratumSignal(BaseModel):
    """Sinal estratificado por subpopulação (sexo, faixa etária, país)."""

    source: str = ""
    stratum_type: str
    stratum_value: str
    drug_event_count: int = 0
    prr: float = 0.0
    ror: float = 0.0
    ic: float = 0.0
    signal_detected: bool = False
    insufficient_data: bool = False


class InvestigationResult(BaseModel):
    """Resultado de investigação profunda: hypothesis + estratificação demográfica."""

    hypothesis: HypothesisResult
    sex_strata: list[StratumSignal] = Field(default_factory=list)
    age_strata: list[StratumSignal] = Field(default_factory=list)
    country_strata: list[StratumSignal] = Field(default_factory=list)
    demographic_summary: str = ""
    meta: MetaInfo


class CompareSignalItem(BaseModel):
    """Comparação de um evento entre duas drogas."""

    event: str
    drug_prr: float
    control_prr: float
    drug_ebgm: float = 0.0
    control_ebgm: float = 0.0
    drug_detected: bool
    control_detected: bool
    ratio: float
    stronger: str


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
