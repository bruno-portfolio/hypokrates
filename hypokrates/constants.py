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


# --- URLs base ---

OPENFDA_BASE_URL = "https://api.fda.gov"
OPENFDA_DRUG_EVENT = f"{OPENFDA_BASE_URL}/drug/event.json"


# --- Cache settings ---


class CacheSettings:
    """TTL padrão por fonte (em segundos)."""

    FAERS_TTL: int = 86_400  # 24h
    VOCAB_TTL: int = 7_776_000  # 90 dias
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
    }
