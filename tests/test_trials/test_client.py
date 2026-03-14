"""Testes para hypokrates.trials.client — HTTP client ClinicalTrials.gov."""

from __future__ import annotations

from typing import Any

import httpx
import pytest
import respx

from hypokrates.config import configure
from hypokrates.constants import TRIALS_BASE_URL
from hypokrates.exceptions import ParseError
from hypokrates.trials.client import TrialsClient
from tests.helpers import load_golden


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
