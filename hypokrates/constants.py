"""Constantes globais do hypokrates."""

from __future__ import annotations

from enum import StrEnum
from typing import ClassVar

__version__ = "0.1.0"

USER_AGENT = f"hypokrates/{__version__}"


class Source(StrEnum):
    """Fontes de dados suportadas."""

    FAERS = "faers"
    DRUGBANK = "drugbank"
    PUBMED = "pubmed"
    OPENALEX = "openalex"
    TRIALS = "trials"
    WHO = "who"
    GBD = "gbd"
    DATASUS = "datasus"
    RXNORM = "rxnorm"
    MESH = "mesh"
    DAILYMED = "dailymed"
    OPENTARGETS = "opentargets"
    CHEMBL = "chembl"


# --- URLs base ---

OPENFDA_BASE_URL = "https://api.fda.gov"
OPENFDA_DRUG_EVENT = f"{OPENFDA_BASE_URL}/drug/event.json"

NCBI_EUTILS_BASE_URL = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils"

RXNORM_BASE_URL = "https://rxnav.nlm.nih.gov/REST"

DAILYMED_BASE_URL = "https://dailymed.nlm.nih.gov/dailymed/services/v2"

TRIALS_BASE_URL = "https://clinicaltrials.gov/api/v2"

OPENTARGETS_GRAPHQL_URL = "https://api.platform.opentargets.org/api/v4/graphql"


# --- Cache settings ---


class CacheSettings:
    """TTL padrão por fonte (em segundos)."""

    FAERS_TTL: int = 86_400  # 24h
    VOCAB_TTL: int = 7_776_000  # 90 dias
    DAILYMED_TTL: int = 2_592_000  # 30 dias
    TRIALS_TTL: int = 86_400  # 24h
    OPENTARGETS_TTL: int = 604_800  # 7 dias
    CHEMBL_TTL: int = 604_800  # 7 dias (releases trimestrais)
    DEFAULT_TTL: int = 86_400  # 24h
    SCHEMA_VERSION: int = 1


# --- HTTP settings ---


class HTTPSettings:
    """Configurações padrão de HTTP."""

    TIMEOUT: float = 30.0
    MAX_RETRIES: int = 3
    BACKOFF_BASE: float = 1.0
    BACKOFF_MAX: float = 60.0
    BACKOFF_FACTOR: float = 2.0

    # Rate limits por fonte (requests por minuto)
    RATE_LIMITS: ClassVar[dict[Source, int]] = {
        Source.FAERS: 40,  # sem API key; com key = 240
        Source.PUBMED: 180,  # 3/s sem key; com key = 600 (10/s)
        Source.RXNORM: 120,
        Source.DAILYMED: 60,  # conservador (nao documentado)
        Source.TRIALS: 50,  # documentado
        Source.OPENTARGETS: 30,  # conservador (nao documentado)
    }
