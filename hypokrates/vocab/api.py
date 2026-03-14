"""API pública do módulo vocab — async-first."""

from __future__ import annotations

import logging
from datetime import UTC, datetime

from hypokrates.models import MetaInfo
from hypokrates.vocab.mesh_client import MeSHClient
from hypokrates.vocab.models import DrugNormResult, MeSHResult
from hypokrates.vocab.parser import (
    parse_mesh_descriptor,
    parse_mesh_search,
    parse_rxnorm_drugs,
)
from hypokrates.vocab.rxnorm_client import RxNormClient

logger = logging.getLogger(__name__)


async def normalize_drug(
    name: str,
    *,
    use_cache: bool = True,
) -> DrugNormResult:
    """Normaliza nome de droga via RxNorm (brand → generic).

    Args:
        name: Nome da droga (brand ou genérico).
        use_cache: Se deve usar cache.

    Returns:
        DrugNormResult com nome genérico, brand names e RXCUI.
    """
    client = RxNormClient()
    try:
        data = await client.search(name, use_cache=use_cache)
    finally:
        await client.close()

    generic_name, brand_names, rxcui = parse_rxnorm_drugs(data)

    return DrugNormResult(
        original=name,
        generic_name=generic_name,
        brand_names=brand_names,
        rxcui=rxcui,
        meta=MetaInfo(
            source="RxNorm",
            query={"name": name},
            total_results=1 if generic_name else 0,
            retrieved_at=datetime.now(UTC),
            disclaimer="Drug normalization via RxNorm (NLM). "
            "Names may not cover all international brands.",
        ),
    )


async def map_to_mesh(
    term: str,
    *,
    use_cache: bool = True,
) -> MeSHResult:
    """Mapeia termo médico para MeSH heading via NCBI.

    Args:
        term: Termo médico para mapear.
        use_cache: Se deve usar cache.

    Returns:
        MeSHResult com MeSH ID, term, e tree numbers.
    """
    client = MeSHClient()
    try:
        search_data = await client.search(term, use_cache=use_cache)
        uids = parse_mesh_search(search_data)

        mesh_id: str | None = None
        mesh_term: str | None = None
        tree_numbers: list[str] = []

        if uids:
            desc_data = await client.fetch_descriptor(uids[0], use_cache=use_cache)
            mesh_id, mesh_term, tree_numbers = parse_mesh_descriptor(desc_data)
    finally:
        await client.close()

    return MeSHResult(
        query=term,
        mesh_id=mesh_id,
        mesh_term=mesh_term,
        tree_numbers=tree_numbers,
        meta=MetaInfo(
            source="NCBI/MeSH",
            query={"term": term},
            total_results=1 if mesh_id else 0,
            retrieved_at=datetime.now(UTC),
            disclaimer="MeSH mapping via NCBI E-utilities. "
            "May not match all synonyms or non-English terms.",
        ),
    )
