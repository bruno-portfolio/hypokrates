"""Modelos do módulo ChEMBL."""

from __future__ import annotations

from pydantic import BaseModel, Field

from hypokrates.models import MetaInfo  # noqa: TC001 — Pydantic needs at runtime


class ChEMBLTarget(BaseModel):
    """Target de uma droga no ChEMBL."""

    target_chembl_id: str
    name: str = ""
    gene_names: list[str] = Field(default_factory=list)
    organism: str = "Homo sapiens"


class MetabolismPathway(BaseModel):
    """Via metabólica individual."""

    enzyme_name: str = ""
    substrate_name: str = ""
    metabolite_name: str = ""
    conversion: str = ""
    organism: str = "Homo sapiens"


class ChEMBLMechanism(BaseModel):
    """Mecanismo de ação de uma droga no ChEMBL."""

    chembl_id: str
    drug_name: str = ""
    mechanism_of_action: str = ""
    action_type: str = ""
    targets: list[ChEMBLTarget] = Field(default_factory=list)
    max_phase: int = 0
    meta: MetaInfo


class ChEMBLMetabolism(BaseModel):
    """Metabolismo de uma droga no ChEMBL."""

    chembl_id: str
    drug_name: str = ""
    pathways: list[MetabolismPathway] = Field(default_factory=list)
    meta: MetaInfo
