"""API pública do módulo PharmGKB — async-first."""

from __future__ import annotations

import logging
from datetime import UTC, datetime

from hypokrates.models import MetaInfo
from hypokrates.pharmgkb.client import PharmGKBClient
from hypokrates.pharmgkb.constants import (
    CHEMICAL_ENDPOINT,
    CLINICAL_ANNOTATION_ENDPOINT,
    GUIDELINE_ENDPOINT,
)
from hypokrates.pharmgkb.models import (
    PharmGKBAnnotation,
    PharmGKBGuideline,
    PharmGKBResult,
)
from hypokrates.pharmgkb.parser import parse_annotations, parse_chemical_id, parse_guidelines

logger = logging.getLogger(__name__)

# Evidence levels ordenados do mais forte ao mais fraco
_EVIDENCE_ORDER = {"1A": 0, "1B": 1, "2A": 2, "2B": 3, "3": 4, "4": 5}


def _level_sort_key(level: str) -> int:
    """Retorna chave de ordenação para evidence level (menor = mais forte)."""
    return _EVIDENCE_ORDER.get(level, 99)


async def pgx_annotations(
    drug: str,
    *,
    min_level: str = "3",
    use_cache: bool = True,
) -> list[PharmGKBAnnotation]:
    """Busca anotações clínicas de farmacogenômica para uma droga.

    Args:
        drug: Nome genérico da droga (e.g., "warfarin").
        min_level: Nível mínimo de evidência (default "3").
            1A = guideline implementada, 4 = case report.
        use_cache: Se deve usar cache.

    Returns:
        Lista de PharmGKBAnnotation ordenada por evidence level.
    """
    client = PharmGKBClient()
    try:
        data = await client.get(
            CLINICAL_ANNOTATION_ENDPOINT,
            {"relatedChemicals.name": drug},
            use_cache=use_cache,
        )
        annotations = parse_annotations(data)

        # Filtrar por nível mínimo de evidência
        min_key = _level_sort_key(min_level)
        filtered = [a for a in annotations if _level_sort_key(a.level_of_evidence) <= min_key]

        # Ordenar por evidence level (mais forte primeiro)
        filtered.sort(key=lambda a: _level_sort_key(a.level_of_evidence))

        return filtered
    finally:
        await client.close()


async def pgx_guidelines(
    drug: str,
    *,
    use_cache: bool = True,
) -> list[PharmGKBGuideline]:
    """Busca dosing guidelines (CPIC/DPWG) para uma droga.

    Args:
        drug: Nome genérico da droga.
        use_cache: Se deve usar cache.

    Returns:
        Lista de PharmGKBGuideline.
    """
    client = PharmGKBClient()
    try:
        data = await client.get(
            GUIDELINE_ENDPOINT,
            {"relatedChemicals.name": drug},
            use_cache=use_cache,
        )
        return parse_guidelines(data)
    finally:
        await client.close()


async def pgx_drug_info(
    drug: str,
    *,
    use_cache: bool = True,
) -> PharmGKBResult:
    """Busca informações farmacogenômicas completas de uma droga.

    Combina anotações clínicas e dosing guidelines em um resultado único.

    Args:
        drug: Nome genérico da droga (e.g., "propofol", "warfarin").
        use_cache: Se deve usar cache.

    Returns:
        PharmGKBResult com annotations, guidelines e metadata.
    """
    client = PharmGKBClient()
    try:
        # 1. Resolver PharmGKB ID
        chem_data = await client.get(
            CHEMICAL_ENDPOINT,
            {"name": drug},
            use_cache=use_cache,
        )
        pharmgkb_id = parse_chemical_id(chem_data)

        # 2. Buscar anotações e guidelines
        ann_data = await client.get(
            CLINICAL_ANNOTATION_ENDPOINT,
            {"relatedChemicals.name": drug},
            use_cache=use_cache,
        )
        guide_data = await client.get(
            GUIDELINE_ENDPOINT,
            {"relatedChemicals.name": drug},
            use_cache=use_cache,
        )

        annotations = parse_annotations(ann_data)
        annotations.sort(key=lambda a: _level_sort_key(a.level_of_evidence))
        guidelines = parse_guidelines(guide_data)

        return PharmGKBResult(
            drug_name=drug,
            pharmgkb_id=pharmgkb_id,
            annotations=annotations,
            guidelines=guidelines,
            meta=MetaInfo(
                source="PharmGKB",
                query={"drug": drug, "pharmgkb_id": pharmgkb_id or ""},
                total_results=len(annotations) + len(guidelines),
                retrieved_at=datetime.now(UTC),
                disclaimer="Pharmacogenomic data from PharmGKB. "
                "Evidence levels: 1A (strongest) to 4 (weakest). "
                "Clinical implementation requires validated genotyping.",
            ),
        )
    finally:
        await client.close()
