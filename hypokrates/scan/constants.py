"""Constantes do módulo scan."""

from __future__ import annotations

from hypokrates.cross.models import HypothesisClassification

DEFAULT_TOP_N = 20
DEFAULT_CONCURRENCY = 5

CLASSIFICATION_WEIGHTS: dict[HypothesisClassification, float] = {
    HypothesisClassification.NOVEL_HYPOTHESIS: 10.0,
    HypothesisClassification.EMERGING_SIGNAL: 5.0,
    HypothesisClassification.KNOWN_ASSOCIATION: 1.0,
    HypothesisClassification.NO_SIGNAL: 0.0,
}

LABEL_NOT_IN_MULTIPLIER: float = 1.5
LABEL_IN_MULTIPLIER: float = 0.5

SCAN_METHODOLOGY = (
    "Automated scan of top FAERS adverse events for a drug. "
    "Each event is cross-referenced with PubMed literature via hypothesis(). "
    "Scoring combines classification weight x signal strength "
    "(average of PRR and ROR lower CI bounds). "
    "Results are ranked by score descending."
)
