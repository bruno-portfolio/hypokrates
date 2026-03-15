"""Constantes específicas do FAERS/OpenFDA."""

from __future__ import annotations

# Endpoints
DRUG_EVENT_ENDPOINT = "/drug/event.json"

# Field mappings para queries OpenFDA
SEARCH_FIELDS = {
    "drug": "patient.drug.openfda.generic_name.exact",
    "brand": "patient.drug.openfda.brand_name.exact",
    "reaction": "patient.reaction.reactionmeddrapt.exact",
    "serious": "serious",
    "sex": "patient.patientsex",
    "country": "occurcountry.exact",
}

# Mapeamento de sexo para código OpenFDA
SEX_MAP = {
    "M": "1",
    "F": "2",
    "UNK": "0",
}

# Count fields para agregações
COUNT_FIELDS = {
    "reaction": "patient.reaction.reactionmeddrapt.exact",
    "drug": "patient.drug.openfda.generic_name.exact",
    "outcome": "patient.reaction.reactionoutcome",
    "country": "occurcountry.exact",
    "age": "patient.patientonsetage",
    "sex": "patient.patientsex",
    "route": "patient.drug.drugadministrationroute",
    "indication": "patient.drug.drugindication.exact",
    "receivedate": "receivedate",
}

# Outcome codes
OUTCOME_MAP = {
    "1": "recovered",
    "2": "recovering",
    "3": "not_recovered",
    "4": "recovered_with_sequelae",
    "5": "fatal",
    "6": "unknown",
}

# Ordem de fallback para resolução de nome de droga
DRUG_FIELD_FALLBACK: list[str] = [
    "patient.drug.openfda.generic_name.exact",
    "patient.drug.openfda.brand_name.exact",
    "patient.drug.medicinalproduct",
]

# Drug characterization codes (ROLE_COD)
DRUG_CHARACTERIZATION_SUSPECT = "1"  # Primary + Secondary suspect
DRUG_CHARACTERIZATION_CONCOMITANT = "2"
DRUG_CHARACTERIZATION_INTERACTING = "3"
DRUG_CHARACTERIZATION_FIELD = "patient.drug.drugcharacterization"

# Co-administration detection
CO_ADMIN_SAMPLE_SIZE: int = 100  # reports para amostrar por par droga+evento
CO_ADMIN_THRESHOLD: float = 3.0  # median suspects > threshold → co_admin_flag
CO_ADMIN_TOP_DRUGS: int = 10  # max co-suspect drugs retornados

# Limites da API
MAX_SKIP = 25_000  # OpenFDA max skip value
MAX_LIMIT = 1_000  # max results per request
DEFAULT_LIMIT = 100
DEFAULT_COUNT_LIMIT = 100
