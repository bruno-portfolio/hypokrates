"""Parsers para respostas da NCBI E-utilities API."""

from __future__ import annotations

import logging
import xml.etree.ElementTree as ET
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


# ---------------------------------------------------------------------------
# EFetch XML parser (abstracts + full metadata)
# ---------------------------------------------------------------------------


def parse_efetch_xml(xml_text: str) -> list[PubMedArticle]:
    """Parseia XML do EFetch → lista de PubMedArticle com abstracts.

    Args:
        xml_text: XML completo retornado pelo EFetch.

    Returns:
        Lista de PubMedArticle (pode conter abstract).
    """
    if not xml_text.strip():
        return []

    try:
        root = ET.fromstring(xml_text)
    except ET.ParseError:
        logger.warning("EFetch: XML inválido")
        return []

    articles: list[PubMedArticle] = []
    for article_elem in root.findall("PubmedArticle"):
        try:
            articles.append(_parse_efetch_article(article_elem))
        except Exception:
            logger.warning("EFetch: falha ao parsear artigo", exc_info=True)

    return articles


def _parse_efetch_article(article_elem: ET.Element) -> PubMedArticle:
    """Parseia um PubmedArticle do EFetch XML."""
    citation = article_elem.find("MedlineCitation")
    if citation is None:
        msg = "MedlineCitation not found"
        raise ValueError(msg)

    pmid_elem = citation.find("PMID")
    pmid = pmid_elem.text.strip() if pmid_elem is not None and pmid_elem.text else ""

    article = citation.find("Article")
    if article is None:
        msg = "Article not found"
        raise ValueError(msg)

    # Title
    title_elem = article.find("ArticleTitle")
    title = "".join(title_elem.itertext()).strip() if title_elem is not None else ""

    # Authors
    authors: list[str] = []
    author_list = article.find("AuthorList")
    if author_list is not None:
        for author in author_list.findall("Author"):
            last = author.findtext("LastName", "")
            fore = author.findtext("ForeName", "")
            if last:
                name = f"{last} {fore}".strip() if fore else last
                authors.append(name)

    # Journal
    journal: str | None = None
    journal_elem = article.find("Journal")
    if journal_elem is not None:
        journal_title = journal_elem.findtext("Title")
        if journal_title:
            journal = journal_title.strip()

    # PubDate
    pub_date: str | None = None
    if journal_elem is not None:
        issue = journal_elem.find("JournalIssue")
        if issue is not None:
            pub_date_elem = issue.find("PubDate")
            if pub_date_elem is not None:
                pub_date = _parse_pub_date(pub_date_elem)

    # DOI (ELocationID ou ArticleIdList fallback)
    doi: str | None = None
    for eloc in article.findall("ELocationID"):
        if eloc.get("EIdType") == "doi" and eloc.text:
            doi = eloc.text.strip()
            break
    if doi is None:
        pubmed_data = article_elem.find("PubmedData")
        if pubmed_data is not None:
            for aid in pubmed_data.findall(".//ArticleId"):
                if aid.get("IdType") == "doi" and aid.text:
                    doi = aid.text.strip()
                    break

    # Abstract
    abstract = _parse_abstract(article.find("Abstract"))

    return PubMedArticle(
        pmid=pmid,
        title=title,
        authors=authors,
        journal=journal,
        pub_date=pub_date,
        doi=doi,
        abstract=abstract,
    )


def _parse_abstract(abstract_elem: ET.Element | None) -> str | None:
    """Parseia Abstract — suporta estruturado e simples."""
    if abstract_elem is None:
        return None

    parts: list[str] = []
    for text_elem in abstract_elem.findall("AbstractText"):
        text = "".join(text_elem.itertext()).strip()
        if not text:
            continue
        label = text_elem.get("Label")
        if label:
            parts.append(f"{label}: {text}")
        else:
            parts.append(text)

    return "\n\n".join(parts) if parts else None


def _parse_pub_date(pub_date_elem: ET.Element) -> str:
    """Parseia PubDate do XML."""
    medline = pub_date_elem.findtext("MedlineDate")
    if medline:
        return medline.strip()

    year = pub_date_elem.findtext("Year", "")
    month = pub_date_elem.findtext("Month", "")

    if year and month:
        return f"{year} {month}"
    return year


# ---------------------------------------------------------------------------
# ESummary JSON parser (legacy — kept for backward compatibility)
# ---------------------------------------------------------------------------


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
