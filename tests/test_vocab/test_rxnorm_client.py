"""Testes para hypokrates.vocab.rxnorm_client — HTTP client RxNorm."""

from __future__ import annotations

from typing import Any

import httpx
import pytest
import respx

from hypokrates.config import configure
from hypokrates.constants import RXNORM_BASE_URL
from hypokrates.exceptions import ParseError, SourceUnavailableError
from hypokrates.vocab.rxnorm_client import RxNormClient
from tests.helpers import load_golden


@pytest.fixture()
def golden_drugs() -> dict[str, Any]:
    return load_golden("vocab", "rxnorm_drugs_ibuprofen.json")


@pytest.fixture()
def golden_not_found() -> dict[str, Any]:
    return load_golden("vocab", "rxnorm_drugs_not_found.json")


class TestRxNormClientSearch:
    """RxNormClient.search — busca, cache, erros."""

    @pytest.fixture(autouse=True)
    def _disable_cache(self) -> None:
        configure(cache_enabled=False)

    @respx.mock
    async def test_search_returns_data(self, golden_drugs: dict[str, Any]) -> None:
        respx.get(url__startswith=f"{RXNORM_BASE_URL}/drugs.json").mock(
            return_value=httpx.Response(200, json=golden_drugs)
        )
        client = RxNormClient()
        try:
            data = await client.search("advil", use_cache=False)
            assert "drugGroup" in data
            assert data["drugGroup"]["name"] == "advil"
        finally:
            await client.close()

    @respx.mock
    async def test_search_not_found(self, golden_not_found: dict[str, Any]) -> None:
        respx.get(url__startswith=f"{RXNORM_BASE_URL}/drugs.json").mock(
            return_value=httpx.Response(200, json=golden_not_found)
        )
        client = RxNormClient()
        try:
            data = await client.search("xyz123", use_cache=False)
            assert "drugGroup" in data
        finally:
            await client.close()

    @respx.mock
    async def test_search_invalid_json(self) -> None:
        """JSON inválido levanta ParseError."""
        respx.get(url__startswith=f"{RXNORM_BASE_URL}/drugs.json").mock(
            return_value=httpx.Response(
                200, content=b"not json", headers={"content-type": "text/plain"}
            )
        )
        client = RxNormClient()
        try:
            with pytest.raises(ParseError):
                await client.search("test", use_cache=False)
        finally:
            await client.close()

    @respx.mock
    async def test_search_missing_druggroup(self) -> None:
        """Response sem 'drugGroup' levanta SourceUnavailableError."""
        respx.get(url__startswith=f"{RXNORM_BASE_URL}/drugs.json").mock(
            return_value=httpx.Response(200, json={"status": "error"})
        )
        client = RxNormClient()
        try:
            with pytest.raises(SourceUnavailableError):
                await client.search("test", use_cache=False)
        finally:
            await client.close()


class TestRxNormClientCache:
    """Cache hit e store paths."""

    @respx.mock
    async def test_search_with_cache_hit(
        self, tmp_path: Any, golden_drugs: dict[str, Any]
    ) -> None:
        """Segunda chamada retorna do cache (sem hit HTTP)."""
        configure(cache_enabled=True, cache_dir=tmp_path)
        route = respx.get(url__startswith=f"{RXNORM_BASE_URL}/drugs.json").mock(
            return_value=httpx.Response(200, json=golden_drugs)
        )
        client = RxNormClient()
        try:
            # Primeira chamada: HTTP
            data1 = await client.search("advil")
            assert route.call_count == 1

            # Segunda chamada: cache hit
            data2 = await client.search("advil")
            assert route.call_count == 1  # não fez segunda request
            assert data1 == data2
        finally:
            await client.close()


class TestRxNormClientClose:
    """Close e get_client."""

    async def test_close_idempotent(self) -> None:
        """Close sem client aberto não falha."""
        configure(cache_enabled=False)
        client = RxNormClient()
        await client.close()
        await client.close()  # segunda vez não falha

    @respx.mock
    async def test_get_client_creates_once(self, golden_drugs: dict[str, Any]) -> None:
        """Múltiplas chamadas reutilizam o mesmo httpx.AsyncClient."""
        configure(cache_enabled=False)
        respx.get(url__startswith=f"{RXNORM_BASE_URL}/drugs.json").mock(
            return_value=httpx.Response(200, json=golden_drugs)
        )
        client = RxNormClient()
        try:
            await client.search("test1", use_cache=False)
            first_client = client._client
            await client.search("test2", use_cache=False)
            assert client._client is first_client
        finally:
            await client.close()
