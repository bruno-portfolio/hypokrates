"""Constantes do módulo vocab."""

from __future__ import annotations

from hypokrates.pubmed.constants import (
    ESEARCH_ENDPOINT,
    ESUMMARY_ENDPOINT,
    TOOL_NAME,
)

RXNORM_DRUGS_ENDPOINT = "/drugs.json"

MESH_DATABASE = "mesh"

# Re-export NCBI constants for local use
__all__ = [
    "ESEARCH_ENDPOINT",
    "ESUMMARY_ENDPOINT",
    "MESH_DATABASE",
    "RXNORM_DRUGS_ENDPOINT",
    "TOOL_NAME",
]
