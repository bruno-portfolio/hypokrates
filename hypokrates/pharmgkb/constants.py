"""Constantes do módulo PharmGKB."""

from __future__ import annotations

PHARMGKB_BASE_URL = "https://api.pharmgkb.org/v1/data"

# Endpoints
CHEMICAL_ENDPOINT = "/chemical"
CLINICAL_ANNOTATION_ENDPOINT = "/clinicalAnnotation"
GUIDELINE_ENDPOINT = "/guidelineAnnotation"

# Rate limit conservador (não documentado, API pública)
PHARMGKB_RATE_PER_MINUTE = 60
