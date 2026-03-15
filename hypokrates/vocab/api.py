"""API pública do módulo vocab — async-first."""

from __future__ import annotations

import logging
from datetime import UTC, datetime

from hypokrates.models import MetaInfo
from hypokrates.vocab.mesh_client import MeSHClient
from hypokrates.vocab.models import DrugNormResult, MeSHResult
from hypokrates.vocab.parser import (
    parse_allrelated_ingredient,
    parse_mesh_descriptor,
    parse_mesh_search,
    parse_rxcui_response,
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

    Fallback chain:
    1. /drugs.json — funciona para genéricos e brands comuns
    2. /rxcui.json + /allrelated.json — resolve SBD/SCD → IN
    3. NOME_PT_EN do ANVISA — resolve nomes internacionais (dipirona→metamizole)

    Args:
        name: Nome da droga (brand ou genérico).
        use_cache: Se deve usar cache.

    Returns:
        DrugNormResult com nome genérico, brand names e RXCUI.
    """
    client = RxNormClient()
    try:
        # Step 1: /drugs.json (endpoint padrão)
        data = await client.search(name, use_cache=use_cache)
        generic_name, brand_names, rxcui = parse_rxnorm_drugs(data)

        # Step 2: /rxcui.json + /allrelated.json (resolve SBD → IN)
        if generic_name is None:
            try:
                rxcui_data = await client.search_by_name(name, use_cache=use_cache)
                found_rxcui = parse_rxcui_response(rxcui_data)
                if found_rxcui:
                    related_data = await client.fetch_allrelated(found_rxcui, use_cache=use_cache)
                    related_name, related_rxcui = parse_allrelated_ingredient(related_data)
                    if related_name:
                        generic_name = related_name
                        rxcui = related_rxcui or found_rxcui
            except Exception:
                logger.debug("RxNorm rxcui/allrelated fallback failed for %s", name)

        # Step 3: NOME_PT_EN — nomes internacionais (dipirona→metamizole)
        if generic_name is None:
            from hypokrates.anvisa.constants import NOME_PT_EN

            pt_name = name.upper().strip()
            en_name = NOME_PT_EN.get(pt_name)
            if en_name:
                logger.info("PT→EN mapping: %s → %s", name, en_name)
                # Tentar resolver o nome EN no RxNorm
                try:
                    en_data = await client.search(en_name, use_cache=use_cache)
                    en_generic, en_brands, en_rxcui = parse_rxnorm_drugs(en_data)
                    if en_generic:
                        generic_name = en_generic
                        brand_names = en_brands
                        rxcui = en_rxcui
                    else:
                        # EN name existe no mapeamento mas não no RxNorm — usar direto
                        generic_name = en_name.lower()
                except Exception:
                    generic_name = en_name.lower()
    finally:
        await client.close()

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
