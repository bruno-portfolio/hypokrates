"""Modelos do módulo vocab."""

from __future__ import annotations

from pydantic import BaseModel, Field

from hypokrates.models import MetaInfo  # noqa: TC001 — Pydantic needs at runtime


class DrugNormResult(BaseModel):
    """Resultado de normalização de nome de droga via RxNorm."""

    original: str
    generic_name: str | None = None
    brand_names: list[str] = Field(default_factory=list)
    rxcui: str | None = None
    meta: MetaInfo


class MeSHResult(BaseModel):
    """Resultado de mapeamento para MeSH heading."""

    query: str
    mesh_id: str | None = None
    mesh_term: str | None = None
    tree_numbers: list[str] = Field(default_factory=list)
    meta: MetaInfo
