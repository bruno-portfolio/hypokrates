"""Constantes do módulo FAERS Bulk."""

from __future__ import annotations

from enum import StrEnum

# Store DuckDB filename (separado do cache HTTP)
FAERS_BULK_DB_FILENAME = "faers_bulk.duckdb"

# Formato ASCII FAERS (pós-2014)
DELIMITER = "$"
ENCODING = "latin-1"
MIN_YEAR = 2014  # Pre-2014 = AERS (formato diferente)

# Batch insert size (controla memoria)
BATCH_SIZE = 10_000


class RoleCod(StrEnum):
    """Drug role codes no FAERS ASCII."""

    PS = "PS"  # Primary Suspect
    SS = "SS"  # Secondary Suspect
    C = "C"  # Concomitant
    I = "I"  # Interacting  # noqa: E741


class RoleCodFilter(StrEnum):
    """Filtros de role para queries."""

    PS_ONLY = "ps_only"  # Apenas Primary Suspect
    SUSPECT = "suspect"  # PS + SS (equivale ao API drugcharacterization=1)
    ALL = "all"  # Todos os roles


# Colunas obrigatórias por arquivo
DEMO_REQUIRED_COLS = ("primaryid", "caseid", "caseversion")
DRUG_REQUIRED_COLS = ("primaryid", "drugname")
REAC_REQUIRED_COLS = ("primaryid", "pt")
