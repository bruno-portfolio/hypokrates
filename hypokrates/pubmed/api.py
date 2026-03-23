from __future__ import annotations

import logging
from datetime import UTC, datetime

from hypokrates.models import MetaInfo
from hypokrates.pubmed.client import PubMedClient
from hypokrates.pubmed.constants import PUBMED_DISCLAIMER
from hypokrates.pubmed.models import PubMedSearchResult
from hypokrates.pubmed.parser import parse_efetch_xml, parse_search_result
from hypokrates.pubmed.search import build_search_term

logger = logging.getLogger(__name__)


async def count_papers(
    drug: str,
    event: str,
    *,
    use_mesh: bool = False,
    use_cache: bool = True,
) -> PubMedSearchResult:
    """Conta papers para um par droga+evento. Uma request (rettype=count).

    Args:
        drug: Nome da droga.
        event: Termo do evento adverso.
        use_mesh: Usar qualificadores MeSH (mais preciso, requer termos válidos).
        use_cache: Se deve usar cache.

    Returns:
        PubMedSearchResult com total_count (sem artigos).
    """
    term = build_search_term(drug, event, use_mesh=use_mesh)

    client = PubMedClient()
    try:
        data = await client.search_count(term, use_cache=use_cache)
    finally:
        await client.close()

    count, _, query_translation = parse_search_result(data)

    return PubMedSearchResult(
        total_count=count,
        query_translation=query_translation,
        meta=MetaInfo(
            source="NCBI/PubMed",
            query={"drug": drug, "event": event, "term": term},
            total_results=count,
            retrieved_at=datetime.now(UTC),
            disclaimer=PUBMED_DISCLAIMER,
        ),
    )


async def search_papers(
    drug: str,
    event: str,
    *,
    limit: int = 10,
    use_mesh: bool = False,
    use_cache: bool = True,
) -> PubMedSearchResult:
    """Busca papers com metadados. Duas requests: ESearch + EFetch.

    Args:
        drug: Nome da droga.
        event: Termo do evento adverso.
        limit: Máximo de artigos retornados.
        use_mesh: Usar qualificadores MeSH (mais preciso).
        use_cache: Se deve usar cache.

    Returns:
        PubMedSearchResult com artigos e metadados.
    """
    term = build_search_term(drug, event, use_mesh=use_mesh)

    client = PubMedClient()
    try:
        search_data = await client.search_ids(term, retmax=limit, use_cache=use_cache)
        count, pmids, query_translation = parse_search_result(search_data)

        articles = []
        if pmids:
            xml_text = await client.fetch_articles(pmids, use_cache=use_cache)
            articles = parse_efetch_xml(xml_text)
    finally:
        await client.close()

    return PubMedSearchResult(
        total_count=count,
        articles=articles,
        query_translation=query_translation,
        meta=MetaInfo(
            source="NCBI/PubMed",
            query={"drug": drug, "event": event, "term": term, "limit": limit},
            total_results=count,
            retrieved_at=datetime.now(UTC),
            disclaimer=PUBMED_DISCLAIMER,
        ),
    )
