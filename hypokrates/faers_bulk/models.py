"""Modelos do módulo FAERS Bulk."""

from __future__ import annotations

from datetime import datetime  # noqa: TC003 — Pydantic needs at runtime

from pydantic import BaseModel, Field


class QuarterInfo(BaseModel):
    """Metadados de um quarter carregado."""

    quarter_key: str  # "2024Q3"
    year: int
    quarter: int
    loaded_at: datetime
    demo_count: int = 0
    drug_count: int = 0
    reac_count: int = 0


class BulkStoreStatus(BaseModel):
    """Status completo do FAERS Bulk store."""

    total_reports: int  # rows em faers_demo
    deduped_cases: int  # rows em faers_dedup
    total_drug_records: int = 0  # rows em faers_drug (real count)
    total_reac_records: int = 0  # rows em faers_reac (real count)
    quarters_loaded: list[QuarterInfo] = Field(default_factory=list)
    oldest_quarter: str | None = None
    newest_quarter: str | None = None


class StrataFilter(BaseModel):
    """Filtro de estratificação demográfica para análise subgrupo."""

    sex: str | None = None  # "M", "F"
    age_group: str | None = None  # "0-17", "18-44", "45-64", "65+"
    reporter_country: str | None = None  # FAERS only

    @property
    def is_empty(self) -> bool:
        """True se nenhum filtro está ativo."""
        return self.sex is None and self.age_group is None and self.reporter_country is None


# Mínimos para strata (subgrupos pequenos produzem PRR absurdo)
MIN_STRATUM_DRUG_EVENT = 3
MIN_STRATUM_DRUG_TOTAL = 10

# Age group ranges
AGE_GROUPS: dict[str, tuple[int, int]] = {
    "0-17": (0, 18),
    "18-44": (18, 45),
    "45-64": (45, 65),
    "65+": (65, 200),
}


class BulkCountResult(BaseModel):
    """Resultado de 4-count deduplicado para um par droga-evento."""

    drug_event: int  # a
    drug_total: int  # a+b
    event_total: int  # a+c
    n_total: int  # N
    deduped: bool = True
    insufficient_data: bool = False
    insufficient_reason: str | None = None
