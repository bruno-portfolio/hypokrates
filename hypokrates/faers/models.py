"""Modelos Pydantic específicos do FAERS."""

from __future__ import annotations

from pydantic import BaseModel, Field

from hypokrates.models import AdverseEvent, Drug, MetaInfo, PatientProfile


class FAERSReaction(BaseModel):
    """Reação adversa de um report FAERS."""

    term: str
    outcome: str | None = None
    version: str | None = None


class FAERSDrug(BaseModel):
    """Medicamento em um report FAERS."""

    name: str
    role: str | None = None  # PS (primary suspect), SS, C, I
    route: str | None = None
    dose: str | None = None
    indication: str | None = None


class FAERSReport(BaseModel):
    """Report individual do FAERS."""

    safety_report_id: str
    receive_date: str | None = None
    receipt_date: str | None = None
    serious: bool = False
    serious_reasons: list[str] = Field(default_factory=list)
    patient: PatientProfile = Field(default_factory=PatientProfile)
    drugs: list[FAERSDrug] = Field(default_factory=list)
    reactions: list[FAERSReaction] = Field(default_factory=list)
    country: str | None = None
    source_type: str | None = None


class FAERSResult(BaseModel):
    """Resultado de uma query FAERS."""

    reports: list[FAERSReport] = Field(default_factory=list)
    events: list[AdverseEvent] = Field(default_factory=list)
    drugs: list[Drug] = Field(default_factory=list)
    meta: MetaInfo


class DrugCount(BaseModel):
    """Droga com contagem de reports (reverse lookup: evento -> drogas)."""

    name: str = Field(description="Nome generico do medicamento")
    count: int = Field(default=0, description="Contagem de reports")


class DrugsByEventResult(BaseModel):
    """Resultado de reverse lookup: evento -> drogas mais reportadas."""

    event: str = Field(description="Termo MedDRA do evento adverso")
    drugs: list[DrugCount] = Field(default_factory=list)
    meta: MetaInfo
