"""ClinicalTrials.gov — busca de trials clínicos por par droga-evento."""

from __future__ import annotations

from hypokrates.trials.api import search_trials
from hypokrates.trials.models import ClinicalTrial, TrialsResult

__all__ = [
    "ClinicalTrial",
    "TrialsResult",
    "search_trials",
]
