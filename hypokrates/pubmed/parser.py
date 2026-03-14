"""Parsers para respostas da NCBI E-utilities API."""

from __future__ import annotations

import logging
from typing import Any

from hypokrates.pubmed.models import PubMedArticle

logger = logging.getLogger(__name__)


def parse_search_result(data: dict[str, Any]) -> tuple[int, list[str], str | None]:
    """Parseia resultado do ESearch.

    Args:
        data: JSON response do ESearch.

    Returns:
        Tupla (count, pmids, query_translation).
    """
    esearch = data.get("esearchresult", {})

    count_raw = esearch.get("count", "0")
    try:
        count = int(count_raw)
    except (ValueError, TypeError):
        count = 0

    id_list: list[str] = esearch.get("idlist", [])
    query_translation: str | None = esearch.get("querytranslation")

    return count, id_list, query_translation


def parse_summaries(data: dict[str, Any]) -> list[PubMedArticle]:
    """Parseia resultado do ESummary.

    Args:
        data: JSON response do ESummary.

    Returns:
        Lista de PubMedArticle com metadados.
    """
    result_block = data.get("result", {})
    uids: list[str] = result_block.get("uids", [])

    articles: list[PubMedArticle] = []
    for uid in uids:
        doc = result_block.get(uid)
        if doc is None or not isinstance(doc, dict):
            logger.warning("ESummary: UID %s sem dados", uid)
            continue
        try:
            articles.append(_parse_single_article(uid, doc))
        except Exception:
            logger.warning("Falha ao parsear artigo PMID %s", uid, exc_info=True)

    return articles


def _parse_single_article(pmid: str, doc: dict[str, Any]) -> PubMedArticle:
    """Parseia um único documento do ESummary."""
    authors_raw = doc.get("authors", [])
    authors: list[str] = []
    if isinstance(authors_raw, list):
        for author in authors_raw:
            if isinstance(author, dict):
                name = author.get("name", "")
                if name:
                    authors.append(name)
            elif isinstance(author, str):
                authors.append(author)

    doi: str | None = None
    article_ids = doc.get("articleids", [])
    if isinstance(article_ids, list):
        for aid in article_ids:
            if isinstance(aid, dict) and aid.get("idtype") == "doi":
                doi = aid.get("value")
                break

    return PubMedArticle(
        pmid=str(pmid),
        title=str(doc.get("title", "")),
        authors=authors,
        journal=doc.get("fulljournalname") or doc.get("source"),
        pub_date=doc.get("pubdate"),
        doi=doi,
    )
