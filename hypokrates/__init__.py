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

from hypokrates import cross, dailymed, faers, pubmed, scan, stats, trials, vocab
from hypokrates.config import configure
from hypokrates.constants import __version__
from hypokrates.cross import HypothesisClassification, HypothesisResult
from hypokrates.dailymed import LabelCheckResult, LabelEventsResult
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
from hypokrates.pubmed import PubMedArticle, PubMedSearchResult
from hypokrates.scan import ScanItem, ScanResult
from hypokrates.trials import ClinicalTrial, TrialsResult
from hypokrates.vocab import DrugNormResult, MeSHResult

__all__ = [
    "CacheError",
    "ClinicalTrial",
    "ConfigurationError",
    "DrugNormResult",
    "EvidenceBlock",
    "HypokratesError",
    "HypothesisClassification",
    "HypothesisResult",
    "LabelCheckResult",
    "LabelEventsResult",
    "Limitation",
    "MeSHResult",
    "NetworkError",
    "ParseError",
    "PubMedArticle",
    "PubMedSearchResult",
    "RateLimitError",
    "ScanItem",
    "ScanResult",
    "SourceUnavailableError",
    "TrialsResult",
    "ValidationError",
    "__version__",
    "configure",
    "cross",
    "dailymed",
    "faers",
    "pubmed",
    "scan",
    "stats",
    "trials",
    "vocab",
]
