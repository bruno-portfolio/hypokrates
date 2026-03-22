"""Cross module — cruzamento de hipóteses FAERS + PubMed."""

from hypokrates.cross.api import hypothesis
from hypokrates.cross.investigate import investigate
from hypokrates.cross.models import (
    HypothesisClassification,
    HypothesisResult,
    InvestigationResult,
    StratumSignal,
)

__all__ = [
    "HypothesisClassification",
    "HypothesisResult",
    "InvestigationResult",
    "StratumSignal",
    "hypothesis",
    "investigate",
]
