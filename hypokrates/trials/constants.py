"""Constantes do módulo ClinicalTrials.gov."""

from __future__ import annotations

# Endpoints ClinicalTrials.gov v2 API
STUDIES_ENDPOINT = "/studies"

# Status considerados "ativos" para contagem
ACTIVE_STATUSES = frozenset(
    {
        "RECRUITING",
        "ACTIVE_NOT_RECRUITING",
        "ENROLLING_BY_INVITATION",
        "NOT_YET_RECRUITING",
    }
)
