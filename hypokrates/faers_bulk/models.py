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


class BulkCountResult(BaseModel):
    """Resultado de 4-count deduplicado para um par droga-evento."""

    drug_event: int  # a
    drug_total: int  # a+b
    event_total: int  # a+c
    n_total: int  # N
    deduped: bool = True
