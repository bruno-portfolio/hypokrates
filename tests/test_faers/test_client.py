"""Testes para hypokrates.faers.client — HTTP client com cache e rate limiting."""

from __future__ import annotations

from typing import Any

import httpx
import respx

from hypokrates.config import configure
from hypokrates.faers.client import FAERSClient


class TestFAERSClientFetch:
    """FAERSClient.fetch — busca, cache, erros."""

    @respx.mock
    async def test_fetch_returns_data(self, golden_faers_adverse_events: dict[str, Any]) -> None:
        configure(cache_enabled=False)
        respx.get(url__startswith="https://api.fda.gov/drug/event.json").mock(
            return_value=httpx.Response(200, json=golden_faers_adverse_events)
        )
        client = FAERSClient()
        try:
            data = await client.fetch(
                'patient.drug.openfda.generic_name.exact:"PROPOFOL"',
                limit=3,
                use_cache=False,
            )
            assert "results" in data
            assert len(data["results"]) == 3
        finally:
            await client.close()

    @respx.mock
    async def test_fetch_handles_no_results(self, golden_faers_no_results: dict[str, Any]) -> None:
        configure(cache_enabled=False)
        respx.get(url__startswith="https://api.fda.gov/drug/event.json").mock(
            return_value=httpx.Response(200, json=golden_faers_no_results)
        )
        client = FAERSClient()
        try:
            data = await client.fetch(
                'patient.drug.openfda.generic_name.exact:"XYZNOTEXIST"',
                use_cache=False,
            )
            assert data["results"] == []
        finally:
            await client.close()

    @respx.mock
    async def test_fetch_includes_results_key(
        self, golden_faers_adverse_events: dict[str, Any]
    ) -> None:
        configure(cache_enabled=False)
        respx.get(url__startswith="https://api.fda.gov/drug/event.json").mock(
            return_value=httpx.Response(200, json=golden_faers_adverse_events)
        )
        client = FAERSClient()
        try:
            data = await client.fetch("test:query", use_cache=False)
            assert "results" in data
            assert "meta" in data
        finally:
            await client.close()


class TestFAERSClientFetchCount:
    """FAERSClient.fetch_count — contagens."""

    @respx.mock
    async def test_fetch_count_returns_data(self, golden_faers_top_events: dict[str, Any]) -> None:
        configure(cache_enabled=False)
        respx.get(url__startswith="https://api.fda.gov/drug/event.json").mock(
            return_value=httpx.Response(200, json=golden_faers_top_events)
        )
        client = FAERSClient()
        try:
            data = await client.fetch_count(
                'patient.drug.openfda.generic_name.exact:"PROPOFOL"',
                "patient.reaction.reactionmeddrapt.exact",
                use_cache=False,
            )
            assert "results" in data
            assert len(data["results"]) == 10
        finally:
            await client.close()


class TestFAERSClientApiKey:
    """Inclusão de API key quando configurada."""

    @respx.mock
    async def test_includes_api_key_when_configured(self) -> None:
        configure(cache_enabled=False, openfda_api_key="test-key-123")
        route = respx.get(url__startswith="https://api.fda.gov/drug/event.json").mock(
            return_value=httpx.Response(
                200, json={"meta": {"results": {"total": 0}}, "results": []}
            )
        )
        client = FAERSClient()
        try:
            await client.fetch("test:query", use_cache=False)
            assert route.called
            request = route.calls[0].request
            assert "api_key=test-key-123" in str(request.url)
        finally:
            await client.close()

    @respx.mock
    async def test_no_api_key_by_default(self) -> None:
        configure(cache_enabled=False)
        route = respx.get(url__startswith="https://api.fda.gov/drug/event.json").mock(
            return_value=httpx.Response(
                200, json={"meta": {"results": {"total": 0}}, "results": []}
            )
        )
        client = FAERSClient()
        try:
            await client.fetch("test:query", use_cache=False)
            request = route.calls[0].request
            assert "api_key" not in str(request.url)
        finally:
            await client.close()
