"""Testes para http/base_client.py."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from hypokrates.exceptions import ParseError
from hypokrates.http.base_client import BaseClient


class _TestClient(BaseClient):
    """Subclasse concreta para testes."""

    def __init__(self) -> None:
        super().__init__(source="test", base_url="https://test.example.com", rate=60)


class TestGetClient:
    """Testes de criação lazy do httpx client."""

    async def test_client_none_until_first_use(self) -> None:
        client = _TestClient()
        assert client._client is None
        await client.close()

    async def test_get_client_creates(self) -> None:
        client = _TestClient()
        http = await client._get_client()
        assert http is not None
        assert client._client is http
        await client.close()

    async def test_get_client_reuses(self) -> None:
        client = _TestClient()
        first = await client._get_client()
        second = await client._get_client()
        assert first is second
        await client.close()


class TestClose:
    """Testes de close e lifecycle."""

    async def test_close_sets_none(self) -> None:
        client = _TestClient()
        _ = await client._get_client()
        assert client._client is not None
        await client.close()
        assert client._client is None

    async def test_close_idempotent(self) -> None:
        client = _TestClient()
        await client.close()
        await client.close()  # nao levanta

    async def test_context_manager(self) -> None:
        async with _TestClient() as client:
            http = await client._get_client()
            assert http is not None
        assert client._client is None


class TestCachedGet:
    """Testes de _cached_get."""

    async def test_cache_hit_returns_cached(self) -> None:
        cached_data = {"result": "from_cache"}
        client = _TestClient()

        mock_store = MagicMock()
        mock_store.aget = AsyncMock(return_value=cached_data)

        with (
            patch("hypokrates.http.base_client.get_config") as mock_cfg,
            patch("hypokrates.http.base_client.CacheStore") as mock_cs,
        ):
            mock_cfg.return_value.cache_enabled = True
            mock_cs.get_instance.return_value = mock_store

            result = await client._cached_get("/test", {"q": "x"})

        assert result == cached_data
        await client.close()

    async def test_cache_miss_fetches_and_stores(self) -> None:
        api_data = {"result": "from_api"}
        mock_response = httpx.Response(
            200,
            json=api_data,
            request=httpx.Request("GET", "https://test.example.com/test"),
        )

        mock_store = MagicMock()
        mock_store.aget = AsyncMock(return_value=None)
        mock_store.aset = AsyncMock()

        client = _TestClient()

        with (
            patch("hypokrates.http.base_client.get_config") as mock_cfg,
            patch("hypokrates.http.base_client.CacheStore") as mock_cs,
            patch(
                "hypokrates.http.base_client.retry_request", new_callable=AsyncMock
            ) as mock_retry,
        ):
            mock_cfg.return_value.cache_enabled = True
            mock_cs.get_instance.return_value = mock_store
            mock_retry.return_value = mock_response

            result = await client._cached_get("/test", {"q": "x"})

        assert result == api_data
        mock_store.aset.assert_called_once()
        await client.close()

    async def test_cache_disabled_skips_cache(self) -> None:
        api_data = {"result": "direct"}
        mock_response = httpx.Response(
            200,
            json=api_data,
            request=httpx.Request("GET", "https://test.example.com/test"),
        )
        client = _TestClient()

        with (
            patch(
                "hypokrates.http.base_client.retry_request", new_callable=AsyncMock
            ) as mock_retry,
            patch("hypokrates.http.base_client.CacheStore") as mock_cs,
        ):
            mock_retry.return_value = mock_response
            result = await client._cached_get("/test", use_cache=False)

        assert result == api_data
        mock_cs.get_instance.assert_not_called()
        await client.close()

    async def test_cache_suffix_alters_key(self) -> None:
        """cache_suffix muda a cache key usada."""
        cached_data = {"result": "suffixed"}
        client = _TestClient()

        mock_store = MagicMock()
        mock_store.aget = AsyncMock(return_value=cached_data)

        with (
            patch("hypokrates.http.base_client.get_config") as mock_cfg,
            patch("hypokrates.http.base_client.CacheStore") as mock_cs,
            patch("hypokrates.http.base_client.cache_key") as mock_ck,
        ):
            mock_cfg.return_value.cache_enabled = True
            mock_cs.get_instance.return_value = mock_store
            mock_ck.return_value = "test:ep/suffix|hash|v1"

            await client._cached_get("/ep", cache_suffix="/suffix")

        mock_ck.assert_called_once_with("test", "/ep/suffix", None)
        await client.close()


class TestParseResponse:
    """Testes de _parse_response."""

    def test_valid_json(self) -> None:
        response = httpx.Response(
            200,
            json={"ok": True},
            request=httpx.Request("GET", "https://example.com"),
        )
        client = _TestClient()
        result = client._parse_response(response)
        assert result == {"ok": True}

    def test_invalid_json_raises(self) -> None:
        response = httpx.Response(
            200,
            content=b"not json",
            headers={"content-type": "text/plain"},
            request=httpx.Request("GET", "https://example.com"),
        )
        client = _TestClient()
        with pytest.raises(ParseError, match="Invalid JSON"):
            client._parse_response(response)
