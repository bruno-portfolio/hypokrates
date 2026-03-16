"""Modelos do módulo PharmGKB."""

from __future__ import annotations

from pydantic import BaseModel, Field

from hypokrates.models import MetaInfo  # noqa: TC001 — Pydantic needs at runtime


class PharmGKBAnnotation(BaseModel):
    """Anotação clínica gene-droga do PharmGKB."""

    accession_id: str = ""
    gene_symbol: str = ""
    level_of_evidence: str = Field(
        default="",
        description="Evidence level: 1A, 1B, 2A, 2B, 3, 4.",
    )
    annotation_types: list[str] = Field(
        default_factory=list,
        description="Types: Toxicity, Dosage, Efficacy, Metabolism/PK, Other.",
    )
    phenotype_categories: list[str] = Field(
        default_factory=list,
        description="Phenotype categories affected.",
    )
    score: float = Field(
        default=0.0,
        description="PharmGKB annotation score.",
    )


class PharmGKBGuideline(BaseModel):
    """Dosing guideline do PharmGKB (CPIC/DPWG/etc)."""

    guideline_id: str = ""
    name: str = ""
    source: str = Field(
        default="",
        description="Guideline source: CPIC, DPWG, CPNDS, RNPGx.",
    )
    genes: list[str] = Field(default_factory=list)
    recommendation: bool = False
    summary: str = ""


class PharmGKBResult(BaseModel):
    """Resultado completo da busca PharmGKB para uma droga."""

    drug_name: str
    pharmgkb_id: str | None = None
    annotations: list[PharmGKBAnnotation] = Field(default_factory=list)
    guidelines: list[PharmGKBGuideline] = Field(default_factory=list)
    meta: MetaInfo
