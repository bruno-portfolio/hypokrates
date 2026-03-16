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

    Busca top 5 UIDs e ranqueia por similaridade com a query
    (token_sort_ratio do rapidfuzz). Evita pegar resultados irrelevantes
    como "Anti-Arrhythmia Agents" para "arrhythmia" ou "MELAS" para
    "lactic acidosis".

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
            # Fetch top 5 candidates and rank by similarity
            candidates: list[tuple[str | None, str | None, list[str], float]] = []
            query_lower = term.lower()
            top_uids = uids[:5]

            for uid in top_uids:
                desc_data = await client.fetch_descriptor(uid, use_cache=use_cache)
                m_id, m_term, m_trees = parse_mesh_descriptor(desc_data)
                if m_term:
                    score = _mesh_similarity(query_lower, m_term.lower())
                    # Boost for shallower (more general) MeSH headings
                    if m_trees:
                        depth = min(len(m_trees[0].split(".")), 5)
                        score += max(0, (5 - depth) * 3)
                    candidates.append((m_id, m_term, m_trees, score))

            if candidates:
                # Best match by similarity
                candidates.sort(key=lambda c: c[3], reverse=True)
                best = candidates[0]
                mesh_id, mesh_term, tree_numbers = best[0], best[1], best[2]
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


def _mesh_similarity(query: str, mesh_term: str) -> float:
    """Score de similaridade entre query e mesh_term.

    Usa rapidfuzz token_sort_ratio se disponível, senão heurística básica.
    """
    try:
        from rapidfuzz.fuzz import token_sort_ratio  # type: ignore[import-not-found,unused-ignore]

        return float(token_sort_ratio(query, mesh_term))
    except ImportError:
        # Fallback: exact prefix/containment heuristic
        if query == mesh_term:
            return 100.0
        if query in mesh_term or mesh_term in query:
            return 80.0
        return 0.0
