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
    count: int = Field(default=0, description="Contagem de reports drug+event")
    total_drug_reports: int | None = Field(
        default=None, description="Total reports da droga (contexto volume)"
    )


class DrugsByEventResult(BaseModel):
    """Resultado de reverse lookup: evento -> drogas mais reportadas."""

    event: str = Field(description="Termo MedDRA do evento adverso")
    drugs: list[DrugCount] = Field(default_factory=list)
    meta: MetaInfo


class CoSuspectProfile(BaseModel):
    """Perfil de co-suspects em reports de um par droga+evento.

    Analisa quantos outros medicamentos são listados como suspect
    nos mesmos reports. Mediana alta (>3) indica co-administração
    procedimental (ex: centro cirúrgico), onde o PRR pode ser
    inflado por onipresença, não por causalidade.
    """

    drug: str = Field(description="Droga-índice")
    event: str = Field(description="Evento adverso")
    sample_size: int = Field(default=0, description="Nº de reports analisados")
    median_suspects: float = Field(
        default=0.0,
        description="Mediana de drogas suspect por report",
    )
    mean_suspects: float = Field(
        default=0.0,
        description="Média de drogas suspect por report",
    )
    max_suspects: int = Field(
        default=0,
        description="Máximo de drogas suspect em um único report",
    )
    top_co_drugs: list[tuple[str, int]] = Field(
        default_factory=list,
        description="Co-suspects mais frequentes (nome, contagem)",
    )
    co_admin_flag: bool = Field(
        default=False,
        description="True se median_suspects > CO_ADMIN_THRESHOLD",
    )
