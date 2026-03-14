"""Domain models compartilhados entre módulos."""

from __future__ import annotations

from datetime import UTC, datetime
from enum import StrEnum

from pydantic import BaseModel, Field


class Sex(StrEnum):
    """Sexo biológico."""

    MALE = "M"
    FEMALE = "F"
    UNKNOWN = "UNK"


class Drug(BaseModel):
    """Representação normalizada de um medicamento."""

    name: str = Field(description="Nome genérico do medicamento")
    brand_names: list[str] = Field(default_factory=list)
    active_ingredients: list[str] = Field(default_factory=list)
    route: str | None = None
    dose: str | None = None


class AdverseEvent(BaseModel):
    """Evento adverso normalizado."""

    term: str = Field(description="Termo do evento adverso (MedDRA preferred term)")
    count: int = Field(default=0, description="Contagem de reports")
    serious: bool | None = None
    outcome: str | None = None


class PatientProfile(BaseModel):
    """Perfil demográfico do paciente."""

    age: float | None = None
    age_unit: str | None = None
    sex: Sex = Sex.UNKNOWN
    weight: float | None = None
    weight_unit: str | None = None


class MetaInfo(BaseModel):
    """Metadados de proveniência de uma resposta."""

    source: str = Field(description="Fonte de dados (e.g., 'OpenFDA/FAERS')")
    query: dict[str, object] = Field(default_factory=dict, description="Parâmetros da consulta")
    total_results: int = Field(default=0)
    cached: bool = Field(default=False)
    retrieved_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    api_version: str | None = None
    disclaimer: str = Field(
        default="This data is from voluntary reports and may contain errors. "
        "Signal does not imply causation."
    )
