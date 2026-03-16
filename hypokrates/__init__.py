"""hypokrates — Normalize and cross-reference global public health data.

Usage:
    import hypokrates as hp

    # Async (default)
    result = await hp.faers.adverse_events("propofol")

    # Sync wrapper
    from hypokrates.sync import faers
    result = faers.adverse_events("propofol")
"""

from __future__ import annotations

from hypokrates import (
    anvisa,
    canada,
    chembl,
    cross,
    dailymed,
    drugbank,
    faers,
    onsides,
    opentargets,
    pharmgkb,
    pubmed,
    scan,
    stats,
    trials,
    vocab,
)
from hypokrates.anvisa import AnvisaMedicamento, AnvisaNomeMapping, AnvisaSearchResult
from hypokrates.canada import CanadaBulkStatus, CanadaSignalResult
from hypokrates.chembl import ChEMBLMechanism, ChEMBLMetabolism, ChEMBLTarget
from hypokrates.config import configure
from hypokrates.constants import __version__
from hypokrates.cross import HypothesisClassification, HypothesisResult
from hypokrates.dailymed import LabelCheckResult, LabelEventsResult
from hypokrates.drugbank import DrugBankInfo, DrugInteraction, DrugTarget
from hypokrates.evidence import EvidenceBlock, Limitation
from hypokrates.exceptions import (
    CacheError,
    ConfigurationError,
    HypokratesError,
    NetworkError,
    ParseError,
    RateLimitError,
    SourceUnavailableError,
    ValidationError,
)
from hypokrates.onsides import OnSIDESEvent, OnSIDESResult
from hypokrates.opentargets import OTAdverseEvent, OTDrugSafety
from hypokrates.pharmgkb import PharmGKBAnnotation, PharmGKBGuideline, PharmGKBResult
from hypokrates.pubmed import PubMedArticle, PubMedSearchResult
from hypokrates.scan import ScanItem, ScanResult
from hypokrates.trials import ClinicalTrial, TrialsResult
from hypokrates.vocab import DrugNormResult, MeSHResult

__all__ = [
    "AnvisaMedicamento",
    "AnvisaNomeMapping",
    "AnvisaSearchResult",
    "CacheError",
    "CanadaBulkStatus",
    "CanadaSignalResult",
    "ChEMBLMechanism",
    "ChEMBLMetabolism",
    "ChEMBLTarget",
    "ClinicalTrial",
    "ConfigurationError",
    "DrugBankInfo",
    "DrugInteraction",
    "DrugNormResult",
    "DrugTarget",
    "EvidenceBlock",
    "HypokratesError",
    "HypothesisClassification",
    "HypothesisResult",
    "LabelCheckResult",
    "LabelEventsResult",
    "Limitation",
    "MeSHResult",
    "NetworkError",
    "OTAdverseEvent",
    "OTDrugSafety",
    "OnSIDESEvent",
    "OnSIDESResult",
    "ParseError",
    "PharmGKBAnnotation",
    "PharmGKBGuideline",
    "PharmGKBResult",
    "PubMedArticle",
    "PubMedSearchResult",
    "RateLimitError",
    "ScanItem",
    "ScanResult",
    "SourceUnavailableError",
    "TrialsResult",
    "ValidationError",
    "__version__",
    "anvisa",
    "canada",
    "chembl",
    "configure",
    "cross",
    "dailymed",
    "drugbank",
    "faers",
    "onsides",
    "opentargets",
    "pharmgkb",
    "pubmed",
    "scan",
    "stats",
    "trials",
    "vocab",
]
