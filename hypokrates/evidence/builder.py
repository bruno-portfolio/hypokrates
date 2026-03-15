"""Builders para criar EvidenceBlock a partir de resultados."""

from __future__ import annotations

from typing import TYPE_CHECKING

from hypokrates.evidence.models import EvidenceBlock, Limitation

if TYPE_CHECKING:
    from hypokrates.models import MetaInfo

_FAERS_LIMITATIONS: list[Limitation] = [
    Limitation.VOLUNTARY_REPORTING,
    Limitation.NO_DENOMINATOR,
    Limitation.DUPLICATE_REPORTS,
    Limitation.MISSING_DATA,
    Limitation.NO_CAUSATION,
]

_DEFAULT_DISCLAIMER = (
    "This data is from voluntary reports and may contain errors. "
    "Signal does not imply causation. Clinical judgment required. "
    "Denominators (N) are snapshots at query time."
)

_SIGNAL_DISCLAIMER = (
    "signal_detected is a screening heuristic (>=2/3 measures significant). "
    "Evaluate individual measures for clinical decisions. "
    "IC uses BCPNN (Norén et al. 2006) with Jeffreys prior (alpha=0.5)."
)


def build_evidence(
    meta: MetaInfo,
    data: dict[str, object],
    *,
    limitations: list[Limitation] | None = None,
    methodology: str | None = None,
    confidence: str | None = None,
) -> EvidenceBlock:
    """Cria EvidenceBlock a partir de MetaInfo e dados."""
    return EvidenceBlock(
        source=meta.source,
        source_version=meta.api_version,
        query=meta.query,
        retrieved_at=meta.retrieved_at,
        cached=meta.cached,
        data=data,
        limitations=limitations or [],
        disclaimer=meta.disclaimer or _DEFAULT_DISCLAIMER,
        methodology=methodology,
        confidence=confidence,
    )


def build_faers_evidence(
    meta: MetaInfo,
    data: dict[str, object],
    *,
    methodology: str | None = None,
    confidence: str | None = None,
) -> EvidenceBlock:
    """Cria EvidenceBlock específico para FAERS (limitações pré-definidas)."""
    return build_evidence(
        meta,
        data,
        limitations=_FAERS_LIMITATIONS,
        methodology=methodology,
        confidence=confidence,
    )
