"""Testes para hypokrates.pubmed.client — mock httpx."""

from __future__ import annotations

from typing import Any

import httpx
import pytest
import respx

from hypokrates.config import configure
from hypokrates.constants import NCBI_EUTILS_BASE_URL
from hypokrates.exceptions import ParseError, SourceUnavailableError
from hypokrates.pubmed.client import PubMedClient
from tests.helpers import load_golden


@pytest.fixture()
def golden_esearch() -> dict[str, Any]:
    return load_golden("pubmed", "esearch_propofol_hepatotoxicity.json")


@pytest.fixture()
def golden_esummary() -> dict[str, Any]:
    return load_golden("pubmed", "esummary_sample.json")


@pytest.fixture()
def golden_count_only() -> dict[str, Any]:
    return load_golden("pubmed", "esearch_count_only.json")


class TestPubMedClientSearchCount:
    """search_count — ESearch com rettype=count."""

    @pytest.fixture(autouse=True)
    def _disable_cache(self) -> None:
        configure(cache_enabled=False)

    @respx.mock
    async def test_search_count_returns_data(self, golden_count_only: dict[str, Any]) -> None:
        respx.get(url__startswith=f"{NCBI_EUTILS_BASE_URL}/esearch.fcgi").mock(
            return_value=httpx.Response(200, json=golden_count_only)
        )
        client = PubMedClient()
        try:
            data = await client.search_count("propofol AND bradycardia", use_cache=False)
            assert "esearchresult" in data
            assert data["esearchresult"]["count"] == "142"
        finally:
            await client.close()

    @respx.mock
    async def test_search_count_api_error(self) -> None:
        respx.get(url__startswith=f"{NCBI_EUTILS_BASE_URL}/esearch.fcgi").mock(
            return_value=httpx.Response(200, json={"error": "API key invalid"})
        )
        client = PubMedClient()
        try:
            with pytest.raises(SourceUnavailableError):
                await client.search_count("test", use_cache=False)
        finally:
            await client.close()


class TestPubMedClientSearchIds:
    """search_ids — ESearch com idlist."""

    @pytest.fixture(autouse=True)
    def _disable_cache(self) -> None:
        configure(cache_enabled=False)

    @respx.mock
    async def test_search_ids_returns_pmids(self, golden_esearch: dict[str, Any]) -> None:
        respx.get(url__startswith=f"{NCBI_EUTILS_BASE_URL}/esearch.fcgi").mock(
            return_value=httpx.Response(200, json=golden_esearch)
        )
        client = PubMedClient()
        try:
            data = await client.search_ids(
                "propofol AND hepatotoxicity", retmax=5, use_cache=False
            )
            ids = data["esearchresult"]["idlist"]
            assert len(ids) == 5
        finally:
            await client.close()

    @respx.mock
    async def test_search_ids_esearch_error(self) -> None:
        """NCBI retorna erro no esearchresult.ERROR."""
        error_data: dict[str, Any] = {"esearchresult": {"ERROR": "Invalid query syntax"}}
        respx.get(url__startswith=f"{NCBI_EUTILS_BASE_URL}/esearch.fcgi").mock(
            return_value=httpx.Response(200, json=error_data)
        )
        client = PubMedClient()
        try:
            with pytest.raises(SourceUnavailableError):
                await client.search_ids("bad[query", use_cache=False)
        finally:
            await client.close()


class TestPubMedClientFetchArticles:
    """fetch_articles — EFetch XML."""

    @pytest.fixture(autouse=True)
    def _disable_cache(self) -> None:
        configure(cache_enabled=False)

    @respx.mock
    async def test_fetch_articles_returns_xml(self) -> None:
        xml = "<PubmedArticleSet><PubmedArticle></PubmedArticle></PubmedArticleSet>"
        respx.get(url__startswith=f"{NCBI_EUTILS_BASE_URL}/efetch.fcgi").mock(
            return_value=httpx.Response(200, text=xml)
        )
        client = PubMedClient()
        try:
            result = await client.fetch_articles(["12345"], use_cache=False)
            assert "PubmedArticleSet" in result
        finally:
            await client.close()

    async def test_fetch_articles_empty_pmids(self) -> None:
        client = PubMedClient()
        try:
            result = await client.fetch_articles([], use_cache=False)
            assert result == ""
        finally:
            await client.close()

    @respx.mock
    async def test_fetch_articles_params_include_retmode_xml(self) -> None:
        xml = "<PubmedArticleSet/>"
        route = respx.get(url__startswith=f"{NCBI_EUTILS_BASE_URL}/efetch.fcgi").mock(
            return_value=httpx.Response(200, text=xml)
        )
        client = PubMedClient()
        try:
            await client.fetch_articles(["111", "222"], use_cache=False)
            request = route.calls.last.request
            assert "retmode=xml" in str(request.url)
            assert "111%2C222" in str(request.url) or "111,222" in str(request.url)
        finally:
            await client.close()


class TestPubMedClientFetchSummaries:
    """fetch_summaries — ESummary (legacy)."""

    @pytest.fixture(autouse=True)
    def _disable_cache(self) -> None:
        configure(cache_enabled=False)

    @respx.mock
    async def test_fetch_summaries_returns_data(self, golden_esummary: dict[str, Any]) -> None:
        respx.get(url__startswith=f"{NCBI_EUTILS_BASE_URL}/esummary.fcgi").mock(
            return_value=httpx.Response(200, json=golden_esummary)
        )
        client = PubMedClient()
        try:
            data = await client.fetch_summaries(
                ["38901234", "37654321", "36543210"], use_cache=False
            )
            assert "result" in data
            assert len(data["result"]["uids"]) == 3
        finally:
            await client.close()

    async def test_fetch_summaries_empty_pmids(self) -> None:
        client = PubMedClient()
        try:
            data = await client.fetch_summaries([], use_cache=False)
            assert data["result"]["uids"] == []
        finally:
            await client.close()

    @respx.mock
    async def test_fetch_summaries_invalid_json(self) -> None:
        respx.get(url__startswith=f"{NCBI_EUTILS_BASE_URL}/esummary.fcgi").mock(
            return_value=httpx.Response(
                200, content=b"not json", headers={"content-type": "text/plain"}
            )
        )
        client = PubMedClient()
        try:
            with pytest.raises(ParseError):
                await client.fetch_summaries(["12345"], use_cache=False)
        finally:
            await client.close()


class TestPubMedClientApiKey:
    """API key e email são incluídos nos params."""

    @respx.mock
    async def test_api_key_in_params(self, golden_count_only: dict[str, Any]) -> None:
        configure(
            cache_enabled=False,
            ncbi_api_key="test_key_123",
            ncbi_email="test@example.com",
        )
        route = respx.get(url__startswith=f"{NCBI_EUTILS_BASE_URL}/esearch.fcgi").mock(
            return_value=httpx.Response(200, json=golden_count_only)
        )
        client = PubMedClient()
        try:
            await client.search_count("test", use_cache=False)
            request = route.calls.last.request
            assert "api_key=test_key_123" in str(request.url)
            assert "email=test%40example.com" in str(request.url)
        finally:
            await client.close()

    @respx.mock
    async def test_tool_param_always_present(self, golden_count_only: dict[str, Any]) -> None:
        configure(cache_enabled=False)
        route = respx.get(url__startswith=f"{NCBI_EUTILS_BASE_URL}/esearch.fcgi").mock(
            return_value=httpx.Response(200, json=golden_count_only)
        )
        client = PubMedClient()
        try:
            await client.search_count("test", use_cache=False)
            request = route.calls.last.request
            assert "tool=hypokrates" in str(request.url)
        finally:
            await client.close()
