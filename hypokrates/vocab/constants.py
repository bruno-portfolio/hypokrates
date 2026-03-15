"""Constantes do módulo vocab."""

from __future__ import annotations

from hypokrates.pubmed.constants import (
    ESEARCH_ENDPOINT,
    ESUMMARY_ENDPOINT,
    TOOL_NAME,
)

RXNORM_DRUGS_ENDPOINT = "/drugs.json"
RXNORM_RXCUI_ENDPOINT = "/rxcui.json"
RXNORM_ALLRELATED_ENDPOINT = "/rxcui/{rxcui}/allrelated.json"

MESH_DATABASE = "mesh"

# Re-export NCBI constants for local use
__all__ = [
    "ESEARCH_ENDPOINT",
    "ESUMMARY_ENDPOINT",
    "MESH_DATABASE",
    "RXNORM_ALLRELATED_ENDPOINT",
    "RXNORM_DRUGS_ENDPOINT",
    "RXNORM_RXCUI_ENDPOINT",
    "TOOL_NAME",
]
