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

from hypokrates import faers
from hypokrates.config import configure
from hypokrates.constants import __version__
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

__all__ = [
    # Exceptions
    "CacheError",
    "ConfigurationError",
    "HypokratesError",
    "NetworkError",
    "ParseError",
    "RateLimitError",
    "SourceUnavailableError",
    "ValidationError",
    "__version__",
    "configure",
    "faers",
]
