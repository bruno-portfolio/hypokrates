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

from hypokrates import cross, faers, pubmed, scan, stats, vocab
from hypokrates.config import configure
from hypokrates.constants import __version__
from hypokrates.cross import HypothesisClassification, HypothesisResult
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
from hypokrates.vocab import DrugNormResult, MeSHResult

__all__ = [
    "CacheError",
    "ConfigurationError",
    "DrugNormResult",
    "EvidenceBlock",
    "HypokratesError",
    "HypothesisClassification",
    "HypothesisResult",
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
    "ValidationError",
    "__version__",
    "configure",
    "cross",
    "faers",
    "pubmed",
    "scan",
    "stats",
    "vocab",
]
