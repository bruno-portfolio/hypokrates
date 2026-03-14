"""Constantes do módulo ChEMBL."""

from __future__ import annotations

CHEMBL_BASE_URL = "https://www.ebi.ac.uk/chembl/api/data"

# Endpoints
MOLECULE_SEARCH_ENDPOINT = "/molecule/search.json"
MECHANISM_ENDPOINT = "/mechanism.json"
METABOLISM_ENDPOINT = "/metabolism.json"
TARGET_ENDPOINT = "/target"

# Rate limit conservador (não documentado, mas generoso)
CHEMBL_RATE_PER_MINUTE = 60
