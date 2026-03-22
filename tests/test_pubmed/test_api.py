"""Testes para hypokrates.pubmed.api — mock client."""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, patch

import pytest

from hypokrates.config import configure
from hypokrates.pubmed.api import count_papers, search_papers
from hypokrates.pubmed.models import PubMedSearchResult


def _mock_search_count(data: dict[str, Any]) -> AsyncMock:
    """Mock para PubMedClient.search_count."""

    async def _side_effect(term: str, *, use_cache: bool = True) -> dict[str, Any]:
        return data

    return AsyncMock(side_effect=_side_effect)


def _mock_search_ids(data: dict[str, Any]) -> AsyncMock:
    """Mock para PubMedClient.search_ids."""

    async def _side_effect(
        term: str, *, retmax: int = 20, use_cache: bool = True
    ) -> dict[str, Any]:
        return data

    return AsyncMock(side_effect=_side_effect)


def _mock_fetch_articles(xml_text: str) -> AsyncMock:
    """Mock para PubMedClient.fetch_articles."""

    async def _side_effect(pmids: list[str], *, use_cache: bool = True) -> str:
        return xml_text

    return AsyncMock(side_effect=_side_effect)


def _mock_fetch_summaries(data: dict[str, Any]) -> AsyncMock:
    """Mock para PubMedClient.fetch_summaries (legacy)."""

    async def _side_effect(pmids: list[str], *, use_cache: bool = True) -> dict[str, Any]:
        return data

    return AsyncMock(side_effect=_side_effect)


class TestCountPapers:
    """count_papers — contagem via ESearch."""

    @pytest.fixture(autouse=True)
    def _disable_cache(self) -> None:
        configure(cache_enabled=False)

    @patch("hypokrates.pubmed.api.PubMedClient")
    async def test_count_papers_returns_result(self, mock_client_cls: Any) -> None:
        instance = mock_client_cls.return_value
        instance.search_count = _mock_search_count(
            {"esearchresult": {"count": "23", "idlist": [], "querytranslation": "test"}}
        )
        instance.close = AsyncMock()

        result = await count_papers("propofol", "hepatotoxicity", use_cache=False)
        assert isinstance(result, PubMedSearchResult)
        assert result.total_count == 23
        assert result.articles == []

    @patch("hypokrates.pubmed.api.PubMedClient")
    async def test_count_papers_zero(self, mock_client_cls: Any) -> None:
        instance = mock_client_cls.return_value
        instance.search_count = _mock_search_count({"esearchresult": {"count": "0", "idlist": []}})
        instance.close = AsyncMock()

        result = await count_papers("xyzdrug", "xyzevent", use_cache=False)
        assert result.total_count == 0

    @patch("hypokrates.pubmed.api.PubMedClient")
    async def test_count_papers_meta(self, mock_client_cls: Any) -> None:
        instance = mock_client_cls.return_value
        instance.search_count = _mock_search_count(
            {"esearchresult": {"count": "10", "idlist": []}}
        )
        instance.close = AsyncMock()

        result = await count_papers("propofol", "bradycardia", use_cache=False)
        assert result.meta.source == "NCBI/PubMed"
        assert result.meta.query["drug"] == "propofol"
        assert result.meta.query["event"] == "bradycardia"
        assert result.meta.retrieved_at is not None

    @patch("hypokrates.pubmed.api.PubMedClient")
    async def test_count_papers_closes_client(self, mock_client_cls: Any) -> None:
        instance = mock_client_cls.return_value
        instance.search_count = _mock_search_count({"esearchresult": {"count": "0", "idlist": []}})
        instance.close = AsyncMock()

        await count_papers("x", "y", use_cache=False)
        instance.close.assert_called_once()


class TestSearchPapers:
    """search_papers — busca com metadados."""

    @pytest.fixture(autouse=True)
    def _disable_cache(self) -> None:
        configure(cache_enabled=False)

    @patch("hypokrates.pubmed.api.PubMedClient")
    async def test_search_papers_with_articles(self, mock_client_cls: Any) -> None:
        xml = """<?xml version="1.0" ?>
        <PubmedArticleSet>
          <PubmedArticle>
            <MedlineCitation>
              <PMID>111</PMID>
              <Article>
                <Journal><Title>J Test</Title>
                  <JournalIssue><PubDate><Year>2024</Year></PubDate></JournalIssue>
                </Journal>
                <ArticleTitle>Article A</ArticleTitle>
                <Abstract><AbstractText>Test abstract A.</AbstractText></Abstract>
                <AuthorList><Author><LastName>Author</LastName><ForeName>X</ForeName></Author></AuthorList>
              </Article>
            </MedlineCitation>
          </PubmedArticle>
          <PubmedArticle>
            <MedlineCitation>
              <PMID>222</PMID>
              <Article>
                <Journal><Title>J Test 2</Title>
                  <JournalIssue><PubDate><Year>2023</Year></PubDate></JournalIssue>
                </Journal>
                <ArticleTitle>Article B</ArticleTitle>
                <AuthorList CompleteYN="N"/>
              </Article>
            </MedlineCitation>
          </PubmedArticle>
        </PubmedArticleSet>"""

        instance = mock_client_cls.return_value
        instance.search_ids = _mock_search_ids(
            {
                "esearchresult": {
                    "count": "23",
                    "idlist": ["111", "222"],
                    "querytranslation": "test",
                }
            }
        )
        instance.fetch_articles = _mock_fetch_articles(xml)
        instance.close = AsyncMock()

        result = await search_papers("propofol", "hepatotoxicity", limit=2, use_cache=False)
        assert isinstance(result, PubMedSearchResult)
        assert result.total_count == 23
        assert len(result.articles) == 2
        assert result.articles[0].pmid == "111"
        assert result.articles[0].title == "Article A"
        assert result.articles[0].abstract == "Test abstract A."

    @patch("hypokrates.pubmed.api.PubMedClient")
    async def test_search_papers_no_results(self, mock_client_cls: Any) -> None:
        instance = mock_client_cls.return_value
        instance.search_ids = _mock_search_ids({"esearchresult": {"count": "0", "idlist": []}})
        instance.close = AsyncMock()

        result = await search_papers("xyzdrug", "xyzevent", use_cache=False)
        assert result.total_count == 0
        assert result.articles == []

    @patch("hypokrates.pubmed.api.PubMedClient")
    async def test_search_papers_with_abstract(self, mock_client_cls: Any) -> None:
        """Abstract é None quando artigo não tem."""
        xml = """<?xml version="1.0" ?>
        <PubmedArticleSet>
          <PubmedArticle>
            <MedlineCitation>
              <PMID>333</PMID>
              <Article>
                <Journal><Title>J</Title>
                  <JournalIssue><PubDate><Year>2024</Year></PubDate></JournalIssue>
                </Journal>
                <ArticleTitle>No Abstract</ArticleTitle>
                <AuthorList CompleteYN="N"/>
              </Article>
            </MedlineCitation>
          </PubmedArticle>
        </PubmedArticleSet>"""

        instance = mock_client_cls.return_value
        instance.search_ids = _mock_search_ids(
            {"esearchresult": {"count": "1", "idlist": ["333"], "querytranslation": "t"}}
        )
        instance.fetch_articles = _mock_fetch_articles(xml)
        instance.close = AsyncMock()

        result = await search_papers("drug", "event", use_cache=False)
        assert result.articles[0].abstract is None

    @patch("hypokrates.pubmed.api.PubMedClient")
    async def test_search_papers_closes_client(self, mock_client_cls: Any) -> None:
        instance = mock_client_cls.return_value
        instance.search_ids = _mock_search_ids({"esearchresult": {"count": "0", "idlist": []}})
        instance.close = AsyncMock()

        await search_papers("x", "y", use_cache=False)
        instance.close.assert_called_once()

    @patch("hypokrates.pubmed.api.PubMedClient")
    async def test_search_papers_mesh_term(self, mock_client_cls: Any) -> None:
        """use_mesh=True → termo com [MeSH]."""
        instance = mock_client_cls.return_value

        captured_terms: list[str] = []

        async def _capture_search_ids(
            term: str, *, retmax: int = 20, use_cache: bool = True
        ) -> dict[str, Any]:
            captured_terms.append(term)
            return {"esearchresult": {"count": "0", "idlist": []}}

        instance.search_ids = AsyncMock(side_effect=_capture_search_ids)
        instance.close = AsyncMock()

        await search_papers("propofol", "bradycardia", use_mesh=True, use_cache=False)
        assert "[MeSH]" in captured_terms[0]
