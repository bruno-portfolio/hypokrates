"""OpenTargets — adverse events com LRT score, safety por target."""

from hypokrates.opentargets.api import drug_adverse_events, drug_safety_score
from hypokrates.opentargets.models import OTAdverseEvent, OTDrugSafety

__all__ = [
    "OTAdverseEvent",
    "OTDrugSafety",
    "drug_adverse_events",
    "drug_safety_score",
]
