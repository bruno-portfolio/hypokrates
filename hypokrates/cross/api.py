"""API pública de cruzamento de hipóteses — async-first."""

from __future__ import annotations

import asyncio
import logging
from datetime import UTC, datetime

from hypokrates.cross.constants import DEFAULT_EMERGING_MAX, DEFAULT_NOVEL_MAX
from hypokrates.cross.models import HypothesisClassification, HypothesisResult
from hypokrates.evidence.builder import build_evidence
from hypokrates.evidence.models import Limitation
from hypokrates.models import MetaInfo
from hypokrates.pubmed import api as pubmed_api
from hypokrates.stats import api as stats_api

logger = logging.getLogger(__name__)

_CROSS_LIMITATIONS: list[Limitation] = [
    Limitation.VOLUNTARY_REPORTING,
    Limitation.NO_DENOMINATOR,
    Limitation.NO_CAUSATION,
]

_CROSS_METHODOLOGY = (
    "Signal detection via FAERS disproportionality (PRR/ROR/IC simplified) "
    "cross-referenced with PubMed literature count. "
    "Classification thresholds are heuristics — adjust for clinical domain."
)


async def hypothesis(
    drug: str,
    event: str,
    *,
    novel_max: int = DEFAULT_NOVEL_MAX,
    emerging_max: int = DEFAULT_EMERGING_MAX,
    literature_limit: int = 5,
    use_mesh: bool = False,
    use_cache: bool = True,
) -> HypothesisResult:
    """Cruza sinal FAERS + literatura PubMed → classificação.

    Args:
        drug: Nome genérico do medicamento.
        event: Termo do evento adverso.
        novel_max: Até N papers = novel_hypothesis (default 0).
        emerging_max: Até N papers = emerging_signal (default 5). Acima = known.
        literature_limit: Máximo de artigos retornados na busca PubMed.
        use_mesh: Usar qualificadores MeSH na busca PubMed (mais preciso).
        use_cache: Se deve usar cache.

    Thresholds são heurísticas — ajuste pro domínio clínico.

    Returns:
        HypothesisResult com classificação, sinal, literatura e evidência.
    """
    # 1+2. FAERS e PubMed são independentes — rodar em paralelo
    signal_result, pubmed_result = await asyncio.gather(
        stats_api.signal(drug, event, use_cache=use_cache),
        pubmed_api.search_papers(
            drug,
            event,
            limit=literature_limit,
            use_mesh=use_mesh,
            use_cache=use_cache,
        ),
    )

    literature_count = pubmed_result.total_count
    articles = pubmed_result.articles

    # 3. Classificar com thresholds
    classification = _classify(
        signal_detected=signal_result.signal_detected,
        literature_count=literature_count,
        novel_max=novel_max,
        emerging_max=emerging_max,
    )

    # 4. Gerar summary
    summary = _build_summary(drug, event, classification, literature_count)

    # 5. Gerar EvidenceBlock
    thresholds_used = {"novel_max": novel_max, "emerging_max": emerging_max}
    evidence = build_evidence(
        MetaInfo(
            source="FAERS+PubMed",
            query={"drug": drug, "event": event},
            total_results=signal_result.table.a,
            retrieved_at=datetime.now(UTC),
            disclaimer="Cross-reference of FAERS signal and PubMed literature. "
            "Classification is a heuristic — clinical validation required.",
        ),
        data={
            "signal_detected": signal_result.signal_detected,
            "faers_reports": signal_result.table.a,
            "literature_count": literature_count,
            "classification": classification.value,
            "thresholds": thresholds_used,
        },
        limitations=_CROSS_LIMITATIONS,
        methodology=_CROSS_METHODOLOGY,
        confidence=_confidence_label(classification),
    )

    return HypothesisResult(
        drug=drug,
        event=event,
        classification=classification,
        signal=signal_result,
        literature_count=literature_count,
        articles=articles,
        evidence=evidence,
        summary=summary,
        thresholds_used=thresholds_used,
    )


def _classify(
    *,
    signal_detected: bool,
    literature_count: int,
    novel_max: int,
    emerging_max: int,
) -> HypothesisClassification:
    """Classifica hipótese com base em sinal e literatura."""
    if not signal_detected:
        return HypothesisClassification.NO_SIGNAL

    if literature_count <= novel_max:
        return HypothesisClassification.NOVEL_HYPOTHESIS
    if literature_count <= emerging_max:
        return HypothesisClassification.EMERGING_SIGNAL
    return HypothesisClassification.KNOWN_ASSOCIATION


def _build_summary(
    drug: str,
    event: str,
    classification: HypothesisClassification,
    literature_count: int,
) -> str:
    """Gera resumo textual da classificação."""
    labels = {
        HypothesisClassification.NOVEL_HYPOTHESIS: "Novel hypothesis",
        HypothesisClassification.EMERGING_SIGNAL: "Emerging signal",
        HypothesisClassification.KNOWN_ASSOCIATION: "Known association",
        HypothesisClassification.NO_SIGNAL: "No signal",
    }
    label = labels[classification]

    parts = [
        f"{label}: {drug.upper()} + {event.upper()}.",
    ]

    if classification == HypothesisClassification.NO_SIGNAL:
        parts.append("No disproportionality signal detected in FAERS.")
    elif classification == HypothesisClassification.NOVEL_HYPOTHESIS:
        parts.append(
            f"FAERS signal detected but no published literature found "
            f"({literature_count} papers). Potential novel finding — requires validation."
        )
    elif classification == HypothesisClassification.EMERGING_SIGNAL:
        parts.append(
            f"FAERS signal detected with limited literature "
            f"({literature_count} papers). Emerging evidence — monitor closely."
        )
    else:
        parts.append(
            f"FAERS signal detected with substantial literature "
            f"({literature_count} papers). Well-documented association."
        )

    return " ".join(parts)


def _confidence_label(classification: HypothesisClassification) -> str:
    """Retorna label de confiança baseado na classificação."""
    labels = {
        HypothesisClassification.NOVEL_HYPOTHESIS: "low — no corroborating literature",
        HypothesisClassification.EMERGING_SIGNAL: "moderate — limited corroborating literature",
        HypothesisClassification.KNOWN_ASSOCIATION: "high — well-documented in literature",
        HypothesisClassification.NO_SIGNAL: "n/a — no signal detected",
    }
    return labels[classification]
