"""Modelos do módulo DrugBank."""

from __future__ import annotations

from pydantic import BaseModel, Field


class DrugTarget(BaseModel):
    """Target (alvo terapêutico) de uma droga."""

    name: str
    gene_name: str = ""
    actions: list[str] = Field(default_factory=list)
    organism: str = "Humans"


class DrugEnzyme(BaseModel):
    """Enzima metabolizadora de uma droga."""

    name: str
    gene_name: str = ""


class DrugInteraction(BaseModel):
    """Interação droga-droga."""

    partner_id: str
    partner_name: str
    description: str = ""


class DrugBankInfo(BaseModel):
    """Informações completas de uma droga no DrugBank."""

    drugbank_id: str
    name: str
    description: str = ""
    mechanism_of_action: str = ""
    pharmacodynamics: str = ""
    categories: list[str] = Field(default_factory=list)
    synonyms: list[str] = Field(default_factory=list)
    targets: list[DrugTarget] = Field(default_factory=list)
    enzymes: list[DrugEnzyme] = Field(default_factory=list)
    interactions: list[DrugInteraction] = Field(default_factory=list)
