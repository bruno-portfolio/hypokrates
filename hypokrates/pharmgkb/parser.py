"""Parser para respostas da API PharmGKB."""

from __future__ import annotations

import logging
from typing import Any

from hypokrates.pharmgkb.models import PharmGKBAnnotation, PharmGKBGuideline

logger = logging.getLogger(__name__)


def parse_chemical_id(data: dict[str, Any]) -> str | None:
    """Extrai PharmGKB ID da resposta /chemical.

    Args:
        data: JSON response envelope.

    Returns:
        PharmGKB accession ID (e.g., "PA450688") ou None.
    """
    items = data.get("data", [])
    if not items:
        return None
    first = items[0] if isinstance(items, list) else items
    result: str | None = first.get("id") or first.get("objCls", {}).get("id")
    return result


def parse_annotations(data: dict[str, Any]) -> list[PharmGKBAnnotation]:
    """Extrai anotações clínicas da resposta /clinicalAnnotation.

    Args:
        data: JSON response envelope.

    Returns:
        Lista de PharmGKBAnnotation.
    """
    items = data.get("data", [])
    if not isinstance(items, list):
        return []

    annotations: list[PharmGKBAnnotation] = []
    for item in items:
        # Extrair gene symbol dos related genes
        gene_symbol = ""
        related_genes = item.get("relatedGenes", [])
        if related_genes and isinstance(related_genes, list):
            gene_symbol = related_genes[0].get("symbol", "")

        # Extrair evidence level
        level = item.get("evidenceLevel", "") or ""

        # Extrair annotation types
        ann_types: list[str] = []
        phenotype_cats: list[str] = []
        phenotypes = item.get("phenotypeCategories", [])
        if isinstance(phenotypes, list):
            for p in phenotypes:
                if isinstance(p, dict):
                    term = p.get("term", "")
                    if term:
                        phenotype_cats.append(term)
                elif isinstance(p, str):
                    phenotype_cats.append(p)
            ann_types = phenotype_cats.copy()

        annotations.append(
            PharmGKBAnnotation(
                accession_id=str(item.get("id", "")),
                gene_symbol=gene_symbol,
                level_of_evidence=level,
                annotation_types=ann_types,
                phenotype_categories=phenotype_cats,
                score=float(item.get("score", 0.0) or 0.0),
            )
        )

    return annotations


def parse_guidelines(data: dict[str, Any]) -> list[PharmGKBGuideline]:
    """Extrai dosing guidelines da resposta /guidelineAnnotation.

    Args:
        data: JSON response envelope.

    Returns:
        Lista de PharmGKBGuideline.
    """
    items = data.get("data", [])
    if not isinstance(items, list):
        return []

    guidelines: list[PharmGKBGuideline] = []
    for item in items:
        # Extrair source
        source = item.get("source", "")

        # Extrair genes
        genes: list[str] = []
        related_genes = item.get("relatedGenes", [])
        if isinstance(related_genes, list):
            for g in related_genes:
                symbol = g.get("symbol", "") if isinstance(g, dict) else str(g)
                if symbol:
                    genes.append(symbol)

        # Extrair recommendation e summary
        name = item.get("name", "")
        recommendation = item.get("recommendation", False) or False
        summary = item.get("summaryMarkdown", "") or item.get("summary", "") or ""

        guidelines.append(
            PharmGKBGuideline(
                guideline_id=str(item.get("id", "")),
                name=name,
                source=source,
                genes=genes,
                recommendation=bool(recommendation),
                summary=summary[:500],
            )
        )

    return guidelines
