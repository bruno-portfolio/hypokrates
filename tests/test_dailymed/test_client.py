"""Testes para hypokrates.dailymed.client — HTTP client DailyMed."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import httpx
import pytest
import respx

from hypokrates.config import configure
from hypokrates.constants import DAILYMED_BASE_URL
from hypokrates.dailymed.client import DailyMedClient
from hypokrates.exceptions import ParseError
from tests.helpers import load_golden

GOLDEN_DATA = Path(__file__).parent.parent / "golden_data"


@pytest.fixture()
def golden_spls() -> dict[str, Any]:
    return load_golden("dailymed", "spls_propofol.json")


@pytest.fixture()
def golden_xml() -> str:
    path = GOLDEN_DATA / "dailymed" / "spl_xml_propofol.xml"
    return path.read_text()


class TestDailyMedClientSearch:
    """DailyMedClient.search_spls — busca, cache, erros."""

    @pytest.fixture(autouse=True)
    def _disable_cache(self) -> None:
        configure(cache_enabled=False)

    @respx.mock
    async def test_search_spls_returns_data(self, golden_spls: dict[str, Any]) -> None:
        respx.get(url__startswith=f"{DAILYMED_BASE_URL}/spls.json").mock(
            return_value=httpx.Response(200, json=golden_spls)
        )
        client = DailyMedClient()
        try:
            data = await client.search_spls("propofol", use_cache=False)
            assert "data" in data
            assert len(data["data"]) == 1
        finally:
            await client.close()

    @respx.mock
    async def test_search_spls_empty(self) -> None:
        respx.get(url__startswith=f"{DAILYMED_BASE_URL}/spls.json").mock(
            return_value=httpx.Response(200, json={"data": [], "metadata": {}})
        )
        client = DailyMedClient()
        try:
            data = await client.search_spls("unknowndrug123", use_cache=False)
            assert data["data"] == []
        finally:
            await client.close()

    @respx.mock
    async def test_search_invalid_json(self) -> None:
        respx.get(url__startswith=f"{DAILYMED_BASE_URL}/spls.json").mock(
            return_value=httpx.Response(
                200, content=b"not json", headers={"content-type": "text/plain"}
            )
        )
        client = DailyMedClient()
        try:
            with pytest.raises(ParseError):
                await client.search_spls("test", use_cache=False)
        finally:
            await client.close()


class TestDailyMedClientFetchXml:
    """DailyMedClient.fetch_spl_xml — XML fetch."""

    @pytest.fixture(autouse=True)
    def _disable_cache(self) -> None:
        configure(cache_enabled=False)

    @respx.mock
    async def test_fetch_xml_returns_text(self, golden_xml: str) -> None:
        respx.get(url__startswith=f"{DAILYMED_BASE_URL}/spls/").mock(
            return_value=httpx.Response(
                200, text=golden_xml, headers={"content-type": "application/xml"}
            )
        )
        client = DailyMedClient()
        try:
            xml = await client.fetch_spl_xml(
                "b169a494-5042-4577-a5e2-f6b48b4c7e21", use_cache=False
            )
            assert "Bradycardia" in xml
            assert "34084-4" in xml
        finally:
            await client.close()


class TestDailyMedClientCache:
    """Cache hit e store paths."""

    @respx.mock
    async def test_search_with_cache_hit(self, tmp_path: Any, golden_spls: dict[str, Any]) -> None:
        configure(cache_enabled=True, cache_dir=tmp_path)
        route = respx.get(url__startswith=f"{DAILYMED_BASE_URL}/spls.json").mock(
            return_value=httpx.Response(200, json=golden_spls)
        )
        client = DailyMedClient()
        try:
            data1 = await client.search_spls("propofol")
            assert route.call_count == 1

            data2 = await client.search_spls("propofol")
            assert route.call_count == 1
            assert data1 == data2
        finally:
            await client.close()

    @respx.mock
    async def test_fetch_xml_with_cache_hit(self, tmp_path: Any, golden_xml: str) -> None:
        configure(cache_enabled=True, cache_dir=tmp_path)
        route = respx.get(url__startswith=f"{DAILYMED_BASE_URL}/spls/").mock(
            return_value=httpx.Response(
                200, text=golden_xml, headers={"content-type": "application/xml"}
            )
        )
        client = DailyMedClient()
        try:
            xml1 = await client.fetch_spl_xml("b169a494-5042-4577-a5e2-f6b48b4c7e21")
            assert route.call_count == 1

            xml2 = await client.fetch_spl_xml("b169a494-5042-4577-a5e2-f6b48b4c7e21")
            assert route.call_count == 1
            assert xml1 == xml2
        finally:
            await client.close()


class TestDailyMedClientClose:
    """Close e get_client."""

    async def test_close_idempotent(self) -> None:
        configure(cache_enabled=False)
        client = DailyMedClient()
        await client.close()
        await client.close()
