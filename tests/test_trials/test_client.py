"""Testes para hypokrates.trials.client — HTTP client ClinicalTrials.gov."""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, patch

import httpx
import pytest
import respx

from hypokrates.config import configure
from hypokrates.constants import TRIALS_BASE_URL
from hypokrates.exceptions import ParseError
from hypokrates.trials.client import TrialsClient
from tests.helpers import load_golden


@pytest.fixture(autouse=True)
def _force_httpx() -> Any:
    """Força o path httpx nos testes (respx não intercepta curl_cffi)."""
    with patch("hypokrates.trials.client._HAS_CURL_CFFI", False):
        yield


@pytest.fixture()
def golden_studies() -> dict[str, Any]:
    return load_golden("trials", "studies_propofol_hypotension.json")


class TestTrialsClientSearch:
    """TrialsClient.search — busca, cache, erros."""

    @pytest.fixture(autouse=True)
    def _disable_cache(self) -> None:
        configure(cache_enabled=False)

    @respx.mock
    async def test_search_returns_data(self, golden_studies: dict[str, Any]) -> None:
        respx.get(url__startswith=f"{TRIALS_BASE_URL}/studies").mock(
            return_value=httpx.Response(200, json=golden_studies)
        )
        client = TrialsClient()
        try:
            data = await client.search("propofol", "hypotension", use_cache=False)
            assert data["totalCount"] == 3
            assert len(data["studies"]) == 3
        finally:
            await client.close()

    @respx.mock
    async def test_search_empty(self) -> None:
        respx.get(url__startswith=f"{TRIALS_BASE_URL}/studies").mock(
            return_value=httpx.Response(200, json={"totalCount": 0, "studies": []})
        )
        client = TrialsClient()
        try:
            data = await client.search("unknowndrug", "unknownevent", use_cache=False)
            assert data["totalCount"] == 0
        finally:
            await client.close()

    @respx.mock
    async def test_search_invalid_json(self) -> None:
        respx.get(url__startswith=f"{TRIALS_BASE_URL}/studies").mock(
            return_value=httpx.Response(
                200, content=b"not json", headers={"content-type": "text/plain"}
            )
        )
        client = TrialsClient()
        try:
            with pytest.raises(ParseError):
                await client.search("test", "test", use_cache=False)
        finally:
            await client.close()


class TestTrialsClientCache:
    """Cache hit e store paths."""

    @respx.mock
    async def test_search_with_cache_hit(
        self, tmp_path: Any, golden_studies: dict[str, Any]
    ) -> None:
        configure(cache_enabled=True, cache_dir=tmp_path)
        route = respx.get(url__startswith=f"{TRIALS_BASE_URL}/studies").mock(
            return_value=httpx.Response(200, json=golden_studies)
        )
        client = TrialsClient()
        try:
            data1 = await client.search("propofol", "hypotension")
            assert route.call_count == 1

            data2 = await client.search("propofol", "hypotension")
            assert route.call_count == 1
            assert data1 == data2
        finally:
            await client.close()


class TestTrialsClientClose:
    """Close e get_client."""

    async def test_close_idempotent(self) -> None:
        configure(cache_enabled=False)
        client = TrialsClient()
        await client.close()
        await client.close()

    async def test_close_cffi_session(self) -> None:
        """Close fecha cffi session se existir."""
        configure(cache_enabled=False)
        client = TrialsClient()
        mock_session = AsyncMock()
        client._cffi_session = mock_session
        await client.close()
        mock_session.close.assert_called_once()
        assert client._cffi_session is None


class TestTrialsClientParseJson:
    """Teste do helper _parse_json."""

    def test_parse_valid_json(self) -> None:
        result = TrialsClient._parse_json('{"totalCount": 0, "studies": []}')
        assert result["totalCount"] == 0

    def test_parse_invalid_json(self) -> None:
        with pytest.raises(ParseError, match="Invalid JSON"):
            TrialsClient._parse_json("not json at all")


class TestTrialsClientFetchCffi:
    """Testes para _fetch_cffi — retry com mock do curl_cffi."""

    @pytest.fixture(autouse=True)
    def _disable_cache(self) -> None:
        configure(cache_enabled=False)

    async def test_cffi_success(self) -> None:
        """Resposta 200 com curl_cffi → retorna dados parseados."""
        client = TrialsClient()
        mock_session = AsyncMock()
        mock_response = AsyncMock()
        mock_response.status_code = 200
        mock_response.text = '{"totalCount": 5, "studies": []}'
        mock_session.get.return_value = mock_response
        client._cffi_session = mock_session

        result = await client._fetch_cffi({"query.intr": "propofol"})
        assert result["totalCount"] == 5
        await client.close()

    async def test_cffi_429_retries(self) -> None:
        """429 na primeira tentativa → retry → sucesso."""
        client = TrialsClient()
        mock_session = AsyncMock()

        resp_429 = AsyncMock()
        resp_429.status_code = 429

        resp_200 = AsyncMock()
        resp_200.status_code = 200
        resp_200.text = '{"totalCount": 0}'

        mock_session.get.side_effect = [resp_429, resp_200]
        client._cffi_session = mock_session

        result = await client._fetch_cffi({"query.intr": "test"})
        assert result["totalCount"] == 0
        await client.close()

    async def test_cffi_429_exhausted(self) -> None:
        """429 em todas as tentativas → RateLimitError."""
        from hypokrates.exceptions import RateLimitError

        client = TrialsClient()
        mock_session = AsyncMock()
        resp_429 = AsyncMock()
        resp_429.status_code = 429
        mock_session.get.return_value = resp_429
        client._cffi_session = mock_session

        with pytest.raises(RateLimitError):
            await client._fetch_cffi({"query.intr": "test"})
        await client.close()

    async def test_cffi_500_retries(self) -> None:
        """500 na primeira → retry → sucesso."""
        client = TrialsClient()
        mock_session = AsyncMock()

        resp_500 = AsyncMock()
        resp_500.status_code = 500

        resp_200 = AsyncMock()
        resp_200.status_code = 200
        resp_200.text = '{"totalCount": 1}'

        mock_session.get.side_effect = [resp_500, resp_200]
        client._cffi_session = mock_session

        result = await client._fetch_cffi({"query.intr": "test"})
        assert result["totalCount"] == 1
        await client.close()

    async def test_cffi_400_raises(self) -> None:
        """400 → NetworkError imediato, sem retry."""
        from hypokrates.exceptions import NetworkError

        client = TrialsClient()
        mock_session = AsyncMock()
        resp_400 = AsyncMock()
        resp_400.status_code = 400
        mock_session.get.return_value = resp_400
        client._cffi_session = mock_session

        with pytest.raises(NetworkError, match="HTTP 400"):
            await client._fetch_cffi({"query.intr": "test"})
        await client.close()

    async def test_cffi_connection_error_retries(self) -> None:
        """OSError na primeira → retry → sucesso."""
        client = TrialsClient()
        mock_session = AsyncMock()

        resp_200 = AsyncMock()
        resp_200.status_code = 200
        resp_200.text = '{"totalCount": 0}'

        mock_session.get.side_effect = [OSError("Connection refused"), resp_200]
        client._cffi_session = mock_session

        result = await client._fetch_cffi({"query.intr": "test"})
        assert result["totalCount"] == 0
        await client.close()

    async def test_cffi_connection_error_exhausted(self) -> None:
        """OSError em todas as tentativas → NetworkError."""
        from hypokrates.exceptions import NetworkError

        client = TrialsClient()
        mock_session = AsyncMock()
        mock_session.get.side_effect = OSError("Connection refused")
        client._cffi_session = mock_session

        with pytest.raises(NetworkError):
            await client._fetch_cffi({"query.intr": "test"})
        await client.close()

    async def test_fetch_dispatches_to_httpx_without_cffi(self) -> None:
        """Sem curl_cffi, _fetch usa _fetch_httpx."""
        configure(cache_enabled=False)
        client = TrialsClient()
        with (
            patch("hypokrates.trials.client._HAS_CURL_CFFI", False),
            patch.object(client, "_fetch_httpx", new_callable=AsyncMock) as mock_httpx,
        ):
            mock_httpx.return_value = {"totalCount": 0}
            result = await client._fetch({"query.intr": "test"})
            assert result["totalCount"] == 0
            mock_httpx.assert_called_once()
        await client.close()
