"""Testes para hypokrates.pubmed.parser — golden data contracts."""

from __future__ import annotations

from typing import Any

import pytest

from hypokrates.pubmed.parser import parse_efetch_xml, parse_search_result, parse_summaries
from tests.helpers import load_golden, load_golden_text


@pytest.fixture()
def golden_esearch() -> dict[str, Any]:
    return load_golden("pubmed", "esearch_propofol_hepatotoxicity.json")


@pytest.fixture()
def golden_esummary() -> dict[str, Any]:
    return load_golden("pubmed", "esummary_sample.json")


@pytest.fixture()
def golden_no_results() -> dict[str, Any]:
    return load_golden("pubmed", "esearch_no_results.json")


@pytest.fixture()
def golden_count_only() -> dict[str, Any]:
    return load_golden("pubmed", "esearch_count_only.json")


class TestParseSearchResult:
    """parse_search_result — contrato com golden data."""

    def test_count_is_int(self, golden_esearch: dict[str, Any]) -> None:
        """count vem como string '23', deve virar int 23."""
        count, _, _ = parse_search_result(golden_esearch)
        assert count == 23
        assert isinstance(count, int)

    def test_returns_pmids(self, golden_esearch: dict[str, Any]) -> None:
        _, pmids, _ = parse_search_result(golden_esearch)
        assert len(pmids) == 5
        assert pmids[0] == "38901234"

    def test_query_translation(self, golden_esearch: dict[str, Any]) -> None:
        _, _, qt = parse_search_result(golden_esearch)
        assert qt is not None
        assert "propofol" in qt

    def test_no_results(self, golden_no_results: dict[str, Any]) -> None:
        count, pmids, _ = parse_search_result(golden_no_results)
        assert count == 0
        assert pmids == []

    def test_count_only(self, golden_count_only: dict[str, Any]) -> None:
        """rettype=count — sem idlist no response."""
        count, pmids, _ = parse_search_result(golden_count_only)
        assert count == 142
        assert pmids == []

    def test_empty_data(self) -> None:
        count, pmids, qt = parse_search_result({})
        assert count == 0
        assert pmids == []
        assert qt is None

    def test_malformed_count(self) -> None:
        """count='abc' → 0."""
        data: dict[str, Any] = {"esearchresult": {"count": "abc"}}
        count, _, _ = parse_search_result(data)
        assert count == 0


class TestParseEfetchXml:
    """parse_efetch_xml — parser de XML EFetch com abstracts."""

    @pytest.fixture()
    def golden_xml(self) -> str:
        return load_golden_text("pubmed", "efetch_sample.xml")

    def test_parses_three_articles(self, golden_xml: str) -> None:
        articles = parse_efetch_xml(golden_xml)
        assert len(articles) == 3

    def test_structured_abstract(self, golden_xml: str) -> None:
        articles = parse_efetch_xml(golden_xml)
        assert articles[0].abstract is not None
        assert "BACKGROUND:" in articles[0].abstract
        assert "CONCLUSIONS:" in articles[0].abstract

    def test_structured_abstract_sections_separated(self, golden_xml: str) -> None:
        articles = parse_efetch_xml(golden_xml)
        assert articles[0].abstract is not None
        assert "\n\n" in articles[0].abstract

    def test_simple_abstract(self, golden_xml: str) -> None:
        articles = parse_efetch_xml(golden_xml)
        assert articles[1].abstract is not None
        assert "Propofol infusion syndrome" in articles[1].abstract

    def test_no_abstract(self, golden_xml: str) -> None:
        articles = parse_efetch_xml(golden_xml)
        assert articles[2].abstract is None

    def test_first_article_metadata(self, golden_xml: str) -> None:
        articles = parse_efetch_xml(golden_xml)
        first = articles[0]
        assert first.pmid == "38901234"
        assert "Propofol" in first.title
        assert first.journal == "Anesthesiology"
        assert first.pub_date == "2024 Jan"
        assert first.doi == "10.1234/anes.2024.001"

    def test_authors_parsed(self, golden_xml: str) -> None:
        articles = parse_efetch_xml(golden_xml)
        assert articles[0].authors == ["Silva Ana B", "Santos Carlos D"]
        assert articles[1].authors == ["Johnson Emily F"]

    def test_no_authors(self, golden_xml: str) -> None:
        articles = parse_efetch_xml(golden_xml)
        assert articles[2].authors == []

    def test_no_doi(self, golden_xml: str) -> None:
        articles = parse_efetch_xml(golden_xml)
        assert articles[2].doi is None

    def test_empty_xml(self) -> None:
        assert parse_efetch_xml("") == []

    def test_malformed_xml(self) -> None:
        assert parse_efetch_xml("<bad") == []

    def test_year_only_pub_date(self, golden_xml: str) -> None:
        """Terceiro artigo tem apenas Year, sem Month."""
        articles = parse_efetch_xml(golden_xml)
        assert articles[2].pub_date == "2022"


class TestParseSummaries:
    """parse_summaries — contrato com golden data."""

    def test_parses_all_articles(self, golden_esummary: dict[str, Any]) -> None:
        articles = parse_summaries(golden_esummary)
        assert len(articles) == 3

    def test_first_article_fields(self, golden_esummary: dict[str, Any]) -> None:
        articles = parse_summaries(golden_esummary)
        first = articles[0]
        assert first.pmid == "38901234"
        assert "Propofol" in first.title
        assert first.journal == "Anesthesiology"
        assert first.pub_date == "2024 Jan"
        assert first.doi == "10.1234/anes.2024.001"

    def test_authors_parsed(self, golden_esummary: dict[str, Any]) -> None:
        articles = parse_summaries(golden_esummary)
        assert articles[0].authors == ["Silva AB", "Santos CD"]
        assert articles[1].authors == ["Johnson EF"]

    def test_article_without_authors(self, golden_esummary: dict[str, Any]) -> None:
        """Artigo sem autores → lista vazia."""
        articles = parse_summaries(golden_esummary)
        assert articles[2].authors == []

    def test_article_without_doi(self, golden_esummary: dict[str, Any]) -> None:
        """Artigo sem DOI nos articleids."""
        articles = parse_summaries(golden_esummary)
        assert articles[2].doi is None

    def test_empty_uids(self) -> None:
        data: dict[str, Any] = {"result": {"uids": []}}
        articles = parse_summaries(data)
        assert articles == []

    def test_empty_data(self) -> None:
        articles = parse_summaries({})
        assert articles == []

    def test_missing_uid_entry(self) -> None:
        """UID na lista mas sem dados → skip com warning."""
        data: dict[str, Any] = {"result": {"uids": ["99999"]}}
        articles = parse_summaries(data)
        assert articles == []
