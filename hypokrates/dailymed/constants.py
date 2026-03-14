"""Constantes do módulo DailyMed."""

from __future__ import annotations

# Endpoints DailyMed REST API v2
SPLS_ENDPOINT = "/spls.json"
SPL_ENDPOINT = "/spls"  # /{set_id}.xml

# LOINC code para seção "Adverse Reactions" em SPL
ADVERSE_REACTIONS_LOINC = "34084-4"

# SPL XML namespace
SPL_NAMESPACE = "{urn:hl7-org:v3}"
