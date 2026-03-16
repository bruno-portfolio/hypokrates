"""Parser para respostas da API PharmGKB."""

from __future__ import annotations

import logging
import re
from typing import Any

from hypokrates.pharmgkb.models import PharmGKBAnnotation, PharmGKBGuideline

logger = logging.getLogger(__name__)


def _strip_html(html: str) -> str:
    """Remove tags HTML simples, retornando texto limpo."""
    return re.sub(r"<[^>]+>", "", html).strip()


def _extract_text(item: dict[str, Any], key: str) -> str:
    """Extrai texto de campo PharmGKB (pode ser str ou dict com 'html')."""
    val = item.get(key)
    if val is None:
        return ""
    if isinstance(val, str):
        return _strip_html(val)
    if isinstance(val, dict):
        raw = str(val.get("html", ""))
        return _strip_html(raw)
    return str(val)


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
        # Extrair gene symbol — real API: location.genes[].symbol
        gene_symbol = ""
        location = item.get("location")
        if isinstance(location, dict):
            genes = location.get("genes", [])
            if genes and isinstance(genes, list):
                first_gene = genes[0]
                if isinstance(first_gene, dict):
                    gene_symbol = first_gene.get("symbol", "")
        # Fallback: golden data format (relatedGenes)
        if not gene_symbol:
            related_genes = item.get("relatedGenes", [])
            if related_genes and isinstance(related_genes, list):
                first_rg = related_genes[0]
                if isinstance(first_rg, dict):
                    gene_symbol = first_rg.get("symbol", "")

        # Extrair evidence level — real API: levelOfEvidence.term
        level = ""
        level_obj = item.get("levelOfEvidence")
        if isinstance(level_obj, dict):
            level = str(level_obj.get("term", ""))
        elif isinstance(level_obj, str):
            level = level_obj
        # Fallback: golden data format (evidenceLevel as string)
        if not level:
            ev = item.get("evidenceLevel", "")
            if isinstance(ev, str):
                level = ev

        # Extrair annotation types — real API: types[] (flat strings)
        ann_types: list[str] = []
        phenotype_cats: list[str] = []
        types_list = item.get("types", [])
        if isinstance(types_list, list):
            for t in types_list:
                if isinstance(t, str) and t:
                    ann_types.append(t)
            phenotype_cats = ann_types.copy()
        # Fallback: golden data format (phenotypeCategories[].term)
        if not ann_types:
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

        # accessionId (real API) vs id (golden data)
        acc_id = str(item.get("accessionId", "")) or str(item.get("id", ""))

        annotations.append(
            PharmGKBAnnotation(
                accession_id=acc_id,
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
        summary = _extract_text(item, "summaryMarkdown") or _extract_text(item, "summary") or ""

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
