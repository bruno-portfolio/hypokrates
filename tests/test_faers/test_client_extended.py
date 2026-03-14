"""Testes estendidos para hypokrates.faers.client — cache, fetch_total, erros."""

from __future__ import annotations

from typing import Any

import httpx
import pytest
import respx

from hypokrates.config import configure
from hypokrates.exceptions import ParseError, SourceUnavailableError
from hypokrates.faers.client import FAERSClient


class TestFAERSClientFetchTotal:
    """FAERSClient.fetch_total — contagem total de reports."""

    @pytest.fixture(autouse=True)
    def _disable_cache(self) -> None:
        configure(cache_enabled=False)

    @respx.mock
    async def test_fetch_total_returns_count(self) -> None:
        respx.get(url__startswith="https://api.fda.gov/drug/event.json").mock(
            return_value=httpx.Response(
                200, json={"meta": {"results": {"total": 12345}}, "results": []}
            )
        )
        client = FAERSClient()
        try:
            total = await client.fetch_total("test:query", use_cache=False)
            assert total == 12345
        finally:
            await client.close()

    @respx.mock
    async def test_fetch_total_no_matches(self) -> None:
        """'No matches found' retorna 0."""
        respx.get(url__startswith="https://api.fda.gov/drug/event.json").mock(
            return_value=httpx.Response(
                200,
                json={"error": {"code": "NOT_FOUND", "message": "No matches found!"}},
            )
        )
        client = FAERSClient()
        try:
            total = await client.fetch_total("nonexistent:drug", use_cache=False)
            assert total == 0
        finally:
            await client.close()

    @respx.mock
    async def test_fetch_total_api_error(self) -> None:
        """Erro real da API levanta SourceUnavailableError."""
        respx.get(url__startswith="https://api.fda.gov/drug/event.json").mock(
            return_value=httpx.Response(
                200,
                json={"error": {"code": "SERVER_ERROR", "message": "Internal error"}},
            )
        )
        client = FAERSClient()
        try:
            with pytest.raises(SourceUnavailableError):
                await client.fetch_total("bad:query", use_cache=False)
        finally:
            await client.close()

    @respx.mock
    async def test_fetch_total_invalid_json(self) -> None:
        respx.get(url__startswith="https://api.fda.gov/drug/event.json").mock(
            return_value=httpx.Response(
                200, content=b"broken", headers={"content-type": "text/plain"}
            )
        )
        client = FAERSClient()
        try:
            with pytest.raises(ParseError):
                await client.fetch_total("test", use_cache=False)
        finally:
            await client.close()

    @respx.mock
    async def test_fetch_total_missing_meta(self) -> None:
        """Response sem meta.results.total retorna 0 (fallback)."""
        respx.get(url__startswith="https://api.fda.gov/drug/event.json").mock(
            return_value=httpx.Response(200, json={"results": []})
        )
        client = FAERSClient()
        try:
            total = await client.fetch_total("test", use_cache=False)
            assert total == 0
        finally:
            await client.close()


class TestFAERSClientCache:
    """Cache hit e store paths para fetch, fetch_count, fetch_total."""

    @respx.mock
    async def test_fetch_cache_hit(
        self, tmp_path: Any, golden_faers_adverse_events: dict[str, Any]
    ) -> None:
        configure(cache_enabled=True, cache_dir=tmp_path)
        route = respx.get(url__startswith="https://api.fda.gov/drug/event.json").mock(
            return_value=httpx.Response(200, json=golden_faers_adverse_events)
        )
        client = FAERSClient()
        try:
            await client.fetch("test:query")
            assert route.call_count == 1
            await client.fetch("test:query")
            assert route.call_count == 1
        finally:
            await client.close()

    @respx.mock
    async def test_fetch_count_cache_hit(
        self, tmp_path: Any, golden_faers_top_events: dict[str, Any]
    ) -> None:
        configure(cache_enabled=True, cache_dir=tmp_path)
        route = respx.get(url__startswith="https://api.fda.gov/drug/event.json").mock(
            return_value=httpx.Response(200, json=golden_faers_top_events)
        )
        client = FAERSClient()
        try:
            await client.fetch_count("test:query", "reaction.term")
            assert route.call_count == 1
            await client.fetch_count("test:query", "reaction.term")
            assert route.call_count == 1
        finally:
            await client.close()

    @respx.mock
    async def test_fetch_total_cache_hit(self, tmp_path: Any) -> None:
        configure(cache_enabled=True, cache_dir=tmp_path)
        route = respx.get(url__startswith="https://api.fda.gov/drug/event.json").mock(
            return_value=httpx.Response(
                200, json={"meta": {"results": {"total": 999}}, "results": []}
            )
        )
        client = FAERSClient()
        try:
            total1 = await client.fetch_total("test:query")
            assert total1 == 999
            assert route.call_count == 1
            total2 = await client.fetch_total("test:query")
            assert total2 == 999
            assert route.call_count == 1
        finally:
            await client.close()


class TestFAERSClientFetchErrors:
    """Erros em fetch e fetch_count."""

    @pytest.fixture(autouse=True)
    def _disable_cache(self) -> None:
        configure(cache_enabled=False)

    @respx.mock
    async def test_fetch_invalid_json(self) -> None:
        respx.get(url__startswith="https://api.fda.gov/drug/event.json").mock(
            return_value=httpx.Response(
                200, content=b"not json", headers={"content-type": "text/plain"}
            )
        )
        client = FAERSClient()
        try:
            with pytest.raises(ParseError):
                await client.fetch("test", use_cache=False)
        finally:
            await client.close()

    @respx.mock
    async def test_fetch_api_error(self) -> None:
        """Erro que não é 'No matches found' levanta SourceUnavailableError."""
        respx.get(url__startswith="https://api.fda.gov/drug/event.json").mock(
            return_value=httpx.Response(
                200,
                json={"error": {"message": "Server overloaded"}},
            )
        )
        client = FAERSClient()
        try:
            with pytest.raises(SourceUnavailableError):
                await client.fetch("test", use_cache=False)
        finally:
            await client.close()

    @respx.mock
    async def test_fetch_count_invalid_json(self) -> None:
        respx.get(url__startswith="https://api.fda.gov/drug/event.json").mock(
            return_value=httpx.Response(
                200, content=b"broken", headers={"content-type": "text/plain"}
            )
        )
        client = FAERSClient()
        try:
            with pytest.raises(ParseError):
                await client.fetch_count("test", "field", use_cache=False)
        finally:
            await client.close()

    @respx.mock
    async def test_fetch_count_api_error(self) -> None:
        respx.get(url__startswith="https://api.fda.gov/drug/event.json").mock(
            return_value=httpx.Response(
                200,
                json={"error": {"message": "Rate limit exceeded"}},
            )
        )
        client = FAERSClient()
        try:
            with pytest.raises(SourceUnavailableError):
                await client.fetch_count("test", "field", use_cache=False)
        finally:
            await client.close()

    @respx.mock
    async def test_fetch_count_no_matches(self) -> None:
        """'No matches found' retorna results vazio."""
        respx.get(url__startswith="https://api.fda.gov/drug/event.json").mock(
            return_value=httpx.Response(
                200,
                json={"error": {"message": "No matches found!"}},
            )
        )
        client = FAERSClient()
        try:
            data = await client.fetch_count("test", "field", use_cache=False)
            assert data["results"] == []
        finally:
            await client.close()


class TestFAERSClientBuildParams:
    """_build_params — skip e count."""

    def test_skip_included_when_positive(self) -> None:
        configure(cache_enabled=False)
        client = FAERSClient()
        params = client._build_params("test:query", skip=10)
        assert params["skip"] == 10

    def test_skip_excluded_when_zero(self) -> None:
        configure(cache_enabled=False)
        client = FAERSClient()
        params = client._build_params("test:query")
        assert "skip" not in params

    def test_count_included(self) -> None:
        configure(cache_enabled=False)
        client = FAERSClient()
        params = client._build_params("test:query", count="reaction.term")
        assert params["count"] == "reaction.term"
