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
    skipped_events: list[str] = Field(default_factory=list)
    mechanism: str | None = None
    interactions_count: int | None = None
    cyp_enzymes: list[str] = Field(default_factory=list)
    meta: MetaInfo
