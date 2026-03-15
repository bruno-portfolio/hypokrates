"""Testes para opentargets/client.py — GraphQL client."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import httpx
import pytest

from hypokrates.exceptions import ParseError
from hypokrates.opentargets.client import OpenTargetsClient


class TestOpenTargetsClient:
    """Testes do client GraphQL."""

    async def test_query_success(self) -> None:
        mock_response = httpx.Response(
            200,
            json={"data": {"search": {"hits": [{"id": "CHEMBL526"}]}}},
        )
        client = OpenTargetsClient()
        with patch.object(client, "_get_client") as mock_get:
            mock_http = AsyncMock()
            mock_http.post.return_value = mock_response
            mock_get.return_value = mock_http

            result = await client.query(
                "query { search { hits { id } } }",
                {"name": "propofol"},
                use_cache=False,
            )

            assert "search" in result
            assert result["search"]["hits"][0]["id"] == "CHEMBL526"

        await client.close()

    async def test_query_graphql_errors(self) -> None:
        mock_response = httpx.Response(
            200,
            json={"errors": [{"message": "Field not found"}]},
        )
        client = OpenTargetsClient()
        with patch.object(client, "_get_client") as mock_get:
            mock_http = AsyncMock()
            mock_http.post.return_value = mock_response
            mock_get.return_value = mock_http

            with pytest.raises(ParseError, match="GraphQL errors"):
                await client.query(
                    "query { bad }",
                    {"name": "test"},
                    use_cache=False,
                )

        await client.close()

    async def test_query_http_error(self) -> None:
        request = httpx.Request("POST", "https://example.com/graphql")
        mock_response = httpx.Response(500, json={}, request=request)
        client = OpenTargetsClient()
        with patch.object(client, "_get_client") as mock_get:
            mock_http = AsyncMock()
            mock_http.post.return_value = mock_response
            mock_get.return_value = mock_http

            with pytest.raises(httpx.HTTPStatusError):
                await client.query(
                    "query { test }",
                    {"name": "test"},
                    use_cache=False,
                )

        await client.close()

    async def test_close_idempotent(self) -> None:
        client = OpenTargetsClient()
        await client.close()
        await client.close()  # Should not raise

    def test_build_cache_params_deterministic(self) -> None:
        params1 = OpenTargetsClient._build_cache_params("query { x }", {"a": "1"})
        params2 = OpenTargetsClient._build_cache_params("query { x }", {"a": "1"})
        assert params1 == params2

    def test_build_cache_params_different_for_different_queries(self) -> None:
        params1 = OpenTargetsClient._build_cache_params("query { x }", {"a": "1"})
        params2 = OpenTargetsClient._build_cache_params("query { y }", {"a": "1"})
        assert params1 != params2

    async def test_query_with_cache(self, tmp_path: object) -> None:
        """Verifica que cache é consultado."""
        from hypokrates.config import configure

        configure(cache_enabled=True, cache_dir=tmp_path)
        mock_response = httpx.Response(
            200,
            json={"data": {"result": True}},
        )
        client = OpenTargetsClient()
        with patch.object(client, "_get_client") as mock_get:
            mock_http = AsyncMock()
            mock_http.post.return_value = mock_response
            mock_get.return_value = mock_http

            # First call — cache miss
            result = await client.query(
                "query { test }",
                {"name": "test"},
                use_cache=True,
            )
            assert result.get("result") is True

        await client.close()

    async def test_parse_response_invalid_json(self) -> None:
        response = httpx.Response(200, content=b"not json", headers={"content-type": "text/plain"})
        client = OpenTargetsClient()
        with pytest.raises(ParseError, match="Invalid JSON"):
            client._parse_response(response)


class TestPostWithRetry:
    """Testes para _post_with_retry — retry, rate limit, timeout."""

    async def test_timeout_retries(self) -> None:
        """Timeout na primeira tentativa → retry → sucesso na segunda."""
        client = OpenTargetsClient()
        mock_http = AsyncMock()
        mock_http.post.side_effect = [
            httpx.TimeoutException("timeout"),
            httpx.Response(200, json={"data": {"ok": True}}),
        ]

        response = await client._post_with_retry(mock_http, {"query": "test"})
        assert response.status_code == 200
        assert mock_http.post.call_count == 2
        await client.close()

    async def test_connect_error_retries(self) -> None:
        """ConnectError na primeira tentativa → retry → sucesso."""
        client = OpenTargetsClient()
        mock_http = AsyncMock()
        mock_http.post.side_effect = [
            httpx.ConnectError("connection refused"),
            httpx.Response(200, json={"data": {"ok": True}}),
        ]

        response = await client._post_with_retry(mock_http, {"query": "test"})
        assert response.status_code == 200
        await client.close()

    async def test_timeout_exhausted_raises(self) -> None:
        """Timeout em todas as tentativas → NetworkError."""
        from hypokrates.exceptions import NetworkError

        client = OpenTargetsClient()
        mock_http = AsyncMock()
        # MAX_RETRIES + 1 timeouts
        mock_http.post.side_effect = httpx.TimeoutException("timeout")

        with pytest.raises(NetworkError):
            await client._post_with_retry(mock_http, {"query": "test"})
        await client.close()

    async def test_rate_limit_429_retries(self) -> None:
        """429 na primeira tentativa → retry → sucesso."""

        client = OpenTargetsClient()
        mock_http = AsyncMock()
        request = httpx.Request("POST", "https://example.com/graphql")
        mock_http.post.side_effect = [
            httpx.Response(429, json={}, request=request),
            httpx.Response(200, json={"data": {"ok": True}}),
        ]

        response = await client._post_with_retry(mock_http, {"query": "test"})
        assert response.status_code == 200
        await client.close()

    async def test_rate_limit_429_with_retry_after(self) -> None:
        """429 com Retry-After header usa o valor do header."""
        client = OpenTargetsClient()
        mock_http = AsyncMock()
        request = httpx.Request("POST", "https://example.com/graphql")
        mock_http.post.side_effect = [
            httpx.Response(429, json={}, headers={"Retry-After": "0.01"}, request=request),
            httpx.Response(200, json={"data": {"ok": True}}),
        ]

        response = await client._post_with_retry(mock_http, {"query": "test"})
        assert response.status_code == 200
        await client.close()

    async def test_rate_limit_exhausted(self) -> None:
        """429 em todas as tentativas → RateLimitError."""
        from hypokrates.exceptions import RateLimitError

        client = OpenTargetsClient()
        mock_http = AsyncMock()
        request = httpx.Request("POST", "https://example.com/graphql")
        mock_http.post.return_value = httpx.Response(429, json={}, request=request)

        with pytest.raises(RateLimitError):
            await client._post_with_retry(mock_http, {"query": "test"})
        await client.close()

    async def test_500_retries(self) -> None:
        """500 na primeira → retry → sucesso."""
        client = OpenTargetsClient()
        mock_http = AsyncMock()
        request = httpx.Request("POST", "https://example.com/graphql")
        mock_http.post.side_effect = [
            httpx.Response(500, json={}, request=request),
            httpx.Response(200, json={"data": {"ok": True}}),
        ]

        response = await client._post_with_retry(mock_http, {"query": "test"})
        assert response.status_code == 200
        await client.close()

    async def test_retry_exhausted_raises(self) -> None:
        """Retry exausto sem sucesso → NetworkError."""
        from hypokrates.exceptions import NetworkError

        client = OpenTargetsClient()
        mock_http = AsyncMock()
        request = httpx.Request("POST", "https://example.com/graphql")
        mock_http.post.return_value = httpx.Response(500, json={}, request=request)

        with pytest.raises((httpx.HTTPStatusError, NetworkError)):
            await client._post_with_retry(mock_http, {"query": "test"})
        await client.close()

    async def test_400_no_retry(self) -> None:
        """400 (não retryable) → raise imediato."""
        client = OpenTargetsClient()
        mock_http = AsyncMock()
        request = httpx.Request("POST", "https://example.com/graphql")
        mock_http.post.return_value = httpx.Response(400, json={}, request=request)

        with pytest.raises(httpx.HTTPStatusError):
            await client._post_with_retry(mock_http, {"query": "test"})
        assert mock_http.post.call_count == 1
        await client.close()
