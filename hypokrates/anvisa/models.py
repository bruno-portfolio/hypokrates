"""Modelos do modulo ANVISA."""

from __future__ import annotations

from pydantic import BaseModel, Field


class AnvisaMedicamento(BaseModel):
    """Medicamento registrado na ANVISA."""

    registro: str
    nome_produto: str
    substancias: list[str] = Field(default_factory=list)
    categoria: str = ""
    referencia: str = ""
    atc: str = ""
    tarja: str = ""
    apresentacoes: list[str] = Field(default_factory=list)
    empresa: str = ""
    image_url: str | None = None


class AnvisaSearchResult(BaseModel):
    """Resultado de busca de medicamentos na ANVISA."""

    query: str
    medicamentos: list[AnvisaMedicamento] = Field(default_factory=list)
    total: int = 0


class AnvisaNomeMapping(BaseModel):
    """Mapeamento de nome PT <-> EN de uma droga."""

    nome_pt: str
    nome_en: str
    source: str = "static"
