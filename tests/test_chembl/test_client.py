"""Testes para chembl/client.py."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import httpx
import pytest

from hypokrates.chembl.client import ChEMBLClient
from hypokrates.exceptions import ParseError


class TestChEMBLClient:
    """Testes do client REST."""

    async def test_get_success(self) -> None:
        mock_response = httpx.Response(
            200,
            json={"molecules": [{"molecule_chembl_id": "CHEMBL526"}]},
            request=httpx.Request("GET", "https://example.com"),
        )
        client = ChEMBLClient()
        with patch(
            "hypokrates.http.base_client.retry_request", new_callable=AsyncMock
        ) as mock_retry:
            mock_retry.return_value = mock_response
            result = await client.get("/molecule/search.json", {"q": "propofol"}, use_cache=False)

        assert result["molecules"][0]["molecule_chembl_id"] == "CHEMBL526"
        await client.close()

    async def test_parse_invalid_json(self) -> None:
        response = httpx.Response(
            200,
            content=b"not json",
            headers={"content-type": "text/plain"},
            request=httpx.Request("GET", "https://example.com"),
        )
        client = ChEMBLClient()
        with pytest.raises(ParseError, match="Invalid JSON"):
            client._parse_response(response)

    async def test_close_idempotent(self) -> None:
        client = ChEMBLClient()
        await client.close()
        await client.close()

    def test_cache_params_deterministic(self) -> None:
        """Duas chamadas com mesmos params geram mesma cache key."""
        from hypokrates.cache.keys import cache_key

        k1 = cache_key("chembl", "/test", {"q": "propofol"})
        k2 = cache_key("chembl", "/test", {"q": "propofol"})
        assert k1 == k2
