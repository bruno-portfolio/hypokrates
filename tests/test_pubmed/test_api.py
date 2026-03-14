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


def _mock_fetch_summaries(data: dict[str, Any]) -> AsyncMock:
    """Mock para PubMedClient.fetch_summaries."""

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
        instance.fetch_summaries = _mock_fetch_summaries(
            {
                "result": {
                    "uids": ["111", "222"],
                    "111": {
                        "uid": "111",
                        "title": "Article A",
                        "pubdate": "2024",
                        "source": "J Test",
                        "authors": [{"name": "Author X", "authtype": "Author"}],
                        "articleids": [],
                    },
                    "222": {
                        "uid": "222",
                        "title": "Article B",
                        "pubdate": "2023",
                        "source": "J Test 2",
                        "authors": [],
                        "articleids": [],
                    },
                }
            }
        )
        instance.close = AsyncMock()

        result = await search_papers("propofol", "hepatotoxicity", limit=2, use_cache=False)
        assert isinstance(result, PubMedSearchResult)
        assert result.total_count == 23
        assert len(result.articles) == 2
        assert result.articles[0].pmid == "111"
        assert result.articles[0].title == "Article A"

    @patch("hypokrates.pubmed.api.PubMedClient")
    async def test_search_papers_no_results(self, mock_client_cls: Any) -> None:
        instance = mock_client_cls.return_value
        instance.search_ids = _mock_search_ids({"esearchresult": {"count": "0", "idlist": []}})
        instance.close = AsyncMock()

        result = await search_papers("xyzdrug", "xyzevent", use_cache=False)
        assert result.total_count == 0
        assert result.articles == []

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
