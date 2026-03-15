"""Modelos do módulo scan."""

from __future__ import annotations

from enum import StrEnum

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
    grouped_terms: list[str] = Field(default_factory=list)
    mechanism: str | None = None
    ot_llr: float | None = None
    volume_flag: bool = Field(
        default=False,
        description="True se a célula a da tabela de contingência excede o limiar. "
        "Não invalida o sinal, mas marca pares cuja interpretação exige auditoria "
        "adicional por risco de stimulated reporting, duplicação, litigation ou notoriedade.",
    )
    is_indication: bool = Field(
        default=False,
        description="True se o evento é uma indicação/condição de base conhecida, "
        "não um efeito adverso. PRR alto reflete perfil de uso, não toxicidade. "
        "Score penalizado para afundar no ranking.",
    )
    coadmin_flag: bool = Field(
        default=False,
        description="True se confounding por co-administração detectado. "
        "Mediana de suspects por report > threshold indica setting procedimental "
        "(ex: centro cirúrgico) onde múltiplas drogas são listadas juntas.",
    )
    coadmin_detail: str | None = Field(
        default=None,
        description="Resumo da análise de co-admin (ex: 'median 5.2 co-suspects').",
    )
    cluster: str = Field(
        default="",
        description="Cluster semântico por sistema clínico "
        "(e.g., 'Cardiovascular', 'Psychiatric'). "
        "Atribuído automaticamente pelo scan para facilitar interpretação.",
    )


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
    groups_applied: bool = False
    filtered_operational_count: int = Field(
        default=0,
        description="Nº de eventos filtrados por serem termos MedDRA operacionais/regulatórios.",
    )
    coadmin_flagged_count: int = Field(
        default=0,
        description="Nº de eventos flaggados como potencial confounding por co-administração.",
    )
    skipped_events: list[str] = Field(default_factory=list)
    mechanism: str | None = None
    interactions_count: int | None = None
    cyp_enzymes: list[str] = Field(default_factory=list)
    meta: MetaInfo


# ---------------------------------------------------------------------------
# compare_class models
# ---------------------------------------------------------------------------


class EventClassification(StrEnum):
    """Classificação de evento em comparação intra-classe."""

    CLASS_EFFECT = "class_effect"
    DRUG_SPECIFIC = "drug_specific"
    DIFFERENTIAL = "differential"


class ClassEventItem(BaseModel):
    """Evento classificado na comparação intra-classe."""

    event: str
    classification: EventClassification
    signals: dict[str, SignalResult]
    drugs_with_signal: list[str]
    drugs_without_signal: list[str]
    strongest_drug: str | None = None
    prr_values: dict[str, float]
    max_prr: float
    median_prr: float
    outlier_drug: str | None = None
    outlier_factor: float | None = None


class ClassCompareResult(BaseModel):
    """Resultado completo de comparação intra-classe."""

    drugs: list[str]
    items: list[ClassEventItem] = Field(default_factory=list)
    class_effect_count: int = 0
    drug_specific_count: int = 0
    differential_count: int = 0
    total_events: int = 0
    class_threshold_used: float
    outlier_factor_used: float
    meta: MetaInfo
