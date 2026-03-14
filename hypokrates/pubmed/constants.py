"""Constantes do módulo PubMed / NCBI E-utilities."""

from __future__ import annotations

ESEARCH_ENDPOINT = "/esearch.fcgi"
ESUMMARY_ENDPOINT = "/esummary.fcgi"
DATABASE = "pubmed"
TOOL_NAME = "hypokrates"

# Rate limit com API key (requests por minuto)
RATE_WITH_KEY: int = 600  # 10/s

DEFAULT_RETMAX: int = 20

PUBMED_DISCLAIMER = (
    "Literature counts are from PubMed/NCBI. Presence of papers does not confirm causation."
)
