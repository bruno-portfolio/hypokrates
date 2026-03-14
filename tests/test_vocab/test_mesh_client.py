"""Testes para hypokrates.vocab.mesh_client — HTTP client MeSH via NCBI E-utilities."""

from __future__ import annotations

from typing import Any

import httpx
import pytest
import respx

from hypokrates.config import configure
from hypokrates.constants import NCBI_EUTILS_BASE_URL
from hypokrates.exceptions import ParseError, SourceUnavailableError
from hypokrates.vocab.mesh_client import MeSHClient
from tests.helpers import load_golden


@pytest.fixture()
def golden_search() -> dict[str, Any]:
    return load_golden("vocab", "mesh_search_aspirin.json")


@pytest.fixture()
def golden_summary() -> dict[str, Any]:
    return load_golden("vocab", "mesh_summary_aspirin.json")


class TestMeSHClientSearch:
    """MeSHClient.search — ESearch db=mesh."""

    @pytest.fixture(autouse=True)
    def _disable_cache(self) -> None:
        configure(cache_enabled=False)

    @respx.mock
    async def test_search_returns_data(self, golden_search: dict[str, Any]) -> None:
        respx.get(url__startswith=f"{NCBI_EUTILS_BASE_URL}/esearch.fcgi").mock(
            return_value=httpx.Response(200, json=golden_search)
        )
        client = MeSHClient()
        try:
            data = await client.search("aspirin", use_cache=False)
            assert "esearchresult" in data
            assert data["esearchresult"]["idlist"] == ["68001241"]
        finally:
            await client.close()

    @respx.mock
    async def test_search_invalid_json(self) -> None:
        """JSON inválido levanta ParseError."""
        respx.get(url__startswith=f"{NCBI_EUTILS_BASE_URL}/esearch.fcgi").mock(
            return_value=httpx.Response(
                200, content=b"not json", headers={"content-type": "text/plain"}
            )
        )
        client = MeSHClient()
        try:
            with pytest.raises(ParseError):
                await client.search("test", use_cache=False)
        finally:
            await client.close()

    @respx.mock
    async def test_search_api_error(self) -> None:
        """Campo 'error' no response levanta SourceUnavailableError."""
        respx.get(url__startswith=f"{NCBI_EUTILS_BASE_URL}/esearch.fcgi").mock(
            return_value=httpx.Response(200, json={"error": "API rate limit exceeded"})
        )
        client = MeSHClient()
        try:
            with pytest.raises(SourceUnavailableError):
                await client.search("test", use_cache=False)
        finally:
            await client.close()

    @respx.mock
    async def test_search_esearch_error(self) -> None:
        """Campo 'ERROR' em esearchresult levanta SourceUnavailableError."""
        respx.get(url__startswith=f"{NCBI_EUTILS_BASE_URL}/esearch.fcgi").mock(
            return_value=httpx.Response(
                200, json={"esearchresult": {"ERROR": "Invalid query syntax"}}
            )
        )
        client = MeSHClient()
        try:
            with pytest.raises(SourceUnavailableError):
                await client.search("bad[query", use_cache=False)
        finally:
            await client.close()


class TestMeSHClientFetchDescriptor:
    """MeSHClient.fetch_descriptor — ESummary db=mesh."""

    @pytest.fixture(autouse=True)
    def _disable_cache(self) -> None:
        configure(cache_enabled=False)

    @respx.mock
    async def test_fetch_descriptor_returns_data(self, golden_summary: dict[str, Any]) -> None:
        respx.get(url__startswith=f"{NCBI_EUTILS_BASE_URL}/esummary.fcgi").mock(
            return_value=httpx.Response(200, json=golden_summary)
        )
        client = MeSHClient()
        try:
            data = await client.fetch_descriptor("68001241", use_cache=False)
            assert "result" in data
            uid_data = data["result"]["68001241"]
            assert uid_data["ds_meshui"] == "D001241"
        finally:
            await client.close()

    @respx.mock
    async def test_fetch_descriptor_invalid_json(self) -> None:
        respx.get(url__startswith=f"{NCBI_EUTILS_BASE_URL}/esummary.fcgi").mock(
            return_value=httpx.Response(
                200, content=b"<xml>not json</xml>", headers={"content-type": "text/xml"}
            )
        )
        client = MeSHClient()
        try:
            with pytest.raises(ParseError):
                await client.fetch_descriptor("12345", use_cache=False)
        finally:
            await client.close()

    @respx.mock
    async def test_fetch_descriptor_api_error(self) -> None:
        respx.get(url__startswith=f"{NCBI_EUTILS_BASE_URL}/esummary.fcgi").mock(
            return_value=httpx.Response(200, json={"error": "UID not found"})
        )
        client = MeSHClient()
        try:
            with pytest.raises(SourceUnavailableError):
                await client.fetch_descriptor("99999", use_cache=False)
        finally:
            await client.close()


class TestMeSHClientCache:
    """Cache hit e store paths."""

    @respx.mock
    async def test_search_cache_hit(self, tmp_path: Any, golden_search: dict[str, Any]) -> None:
        configure(cache_enabled=True, cache_dir=tmp_path)
        route = respx.get(url__startswith=f"{NCBI_EUTILS_BASE_URL}/esearch.fcgi").mock(
            return_value=httpx.Response(200, json=golden_search)
        )
        client = MeSHClient()
        try:
            await client.search("aspirin")
            assert route.call_count == 1
            await client.search("aspirin")
            assert route.call_count == 1
        finally:
            await client.close()

    @respx.mock
    async def test_fetch_descriptor_cache_hit(
        self, tmp_path: Any, golden_summary: dict[str, Any]
    ) -> None:
        configure(cache_enabled=True, cache_dir=tmp_path)
        route = respx.get(url__startswith=f"{NCBI_EUTILS_BASE_URL}/esummary.fcgi").mock(
            return_value=httpx.Response(200, json=golden_summary)
        )
        client = MeSHClient()
        try:
            await client.fetch_descriptor("68001241")
            assert route.call_count == 1
            await client.fetch_descriptor("68001241")
            assert route.call_count == 1
        finally:
            await client.close()


class TestMeSHClientAuth:
    """API key e email nos parâmetros."""

    @respx.mock
    async def test_api_key_in_search_params(self, golden_search: dict[str, Any]) -> None:
        configure(
            cache_enabled=False,
            ncbi_api_key="test_key_123",
            ncbi_email="test@example.com",
        )
        route = respx.get(url__startswith=f"{NCBI_EUTILS_BASE_URL}/esearch.fcgi").mock(
            return_value=httpx.Response(200, json=golden_search)
        )
        client = MeSHClient()
        try:
            await client.search("aspirin", use_cache=False)
            request = route.calls.last.request
            url_str = str(request.url)
            assert "api_key=test_key_123" in url_str
            assert "email=test%40example.com" in url_str
            assert "db=mesh" in url_str
        finally:
            await client.close()

    @respx.mock
    async def test_no_api_key_by_default(self, golden_search: dict[str, Any]) -> None:
        configure(cache_enabled=False)
        route = respx.get(url__startswith=f"{NCBI_EUTILS_BASE_URL}/esearch.fcgi").mock(
            return_value=httpx.Response(200, json=golden_search)
        )
        client = MeSHClient()
        try:
            await client.search("aspirin", use_cache=False)
            url_str = str(route.calls.last.request.url)
            assert "api_key" not in url_str
        finally:
            await client.close()


class TestMeSHClientClose:
    """Close e lifecycle."""

    async def test_close_idempotent(self) -> None:
        configure(cache_enabled=False)
        client = MeSHClient()
        await client.close()
        await client.close()

    @respx.mock
    async def test_get_client_creates_once(self, golden_search: dict[str, Any]) -> None:
        configure(cache_enabled=False)
        respx.get(url__startswith=f"{NCBI_EUTILS_BASE_URL}/esearch.fcgi").mock(
            return_value=httpx.Response(200, json=golden_search)
        )
        client = MeSHClient()
        try:
            await client.search("term1", use_cache=False)
            first_client = client._client
            await client.search("term2", use_cache=False)
            assert client._client is first_client
        finally:
            await client.close()
