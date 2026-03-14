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
        with pytest.raises(ParseError, match="Invalid JSON"):
            OpenTargetsClient._parse_response(response)
