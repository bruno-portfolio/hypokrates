"""Constantes do módulo DailyMed."""

from __future__ import annotations

# Endpoints DailyMed REST API v2
SPLS_ENDPOINT = "/spls.json"
SPL_ENDPOINT = "/spls"  # /{set_id}.xml

# LOINC code para seção "Adverse Reactions" em SPL
ADVERSE_REACTIONS_LOINC = "34084-4"

# LOINC codes para outras seções de segurança
BOXED_WARNING_LOINC = "34066-1"
WARNINGS_LOINC = "34071-1"
WARNINGS_PRECAUTIONS_LOINC = "43685-7"

# Todos os LOINC codes de segurança relevantes
SAFETY_LOINC_CODES: dict[str, str] = {
    ADVERSE_REACTIONS_LOINC: "Adverse Reactions",
    BOXED_WARNING_LOINC: "Boxed Warning",
    WARNINGS_LOINC: "Warnings",
    WARNINGS_PRECAUTIONS_LOINC: "Warnings and Precautions",
}

# LOINC code para seção "Indications and Usage"
INDICATIONS_LOINC = "34067-9"

# SPL XML namespace
SPL_NAMESPACE = "{urn:hl7-org:v3}"
