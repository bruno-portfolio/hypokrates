"""Testes para hypokrates.sync — wrapper síncrono funciona em ambos os code paths."""

from __future__ import annotations

from typing import Any

import httpx
import pytest
import respx

from hypokrates.config import configure
from hypokrates.exceptions import NetworkError
from hypokrates.faers.models import FAERSResult
from hypokrates.sync import faers


class TestSyncWrapper:
    """Sync wrapper funciona em ambos os code paths."""

    @respx.mock
    def test_sync_adverse_events(self, golden_faers_adverse_events: dict[str, Any]) -> None:
        configure(cache_enabled=False)
        respx.get(url__startswith="https://api.fda.gov/drug/event.json").mock(
            return_value=httpx.Response(200, json=golden_faers_adverse_events)
        )
        result = faers.adverse_events("propofol", use_cache=False)
        assert len(result.reports) == 3

    @respx.mock
    def test_sync_top_events(self, golden_faers_top_events: dict[str, Any]) -> None:
        configure(cache_enabled=False)
        respx.get(url__startswith="https://api.fda.gov/drug/event.json").mock(
            return_value=httpx.Response(200, json=golden_faers_top_events)
        )
        result = faers.top_events("propofol", use_cache=False)
        assert len(result.events) == 10

    @respx.mock
    def test_sync_compare(self, golden_faers_top_events: dict[str, Any]) -> None:
        configure(cache_enabled=False)
        respx.get(url__startswith="https://api.fda.gov/drug/event.json").mock(
            return_value=httpx.Response(200, json=golden_faers_top_events)
        )
        results = faers.compare(["propofol", "ketamine"], use_cache=False)
        assert "propofol" in results
        assert "ketamine" in results

    @respx.mock
    def test_sync_preserves_result_type(self, golden_faers_adverse_events: dict[str, Any]) -> None:
        """Retorno é FAERSResult, não coroutine."""
        configure(cache_enabled=False)
        respx.get(url__startswith="https://api.fda.gov/drug/event.json").mock(
            return_value=httpx.Response(200, json=golden_faers_adverse_events)
        )
        result = faers.adverse_events("propofol", use_cache=False)
        assert isinstance(result, FAERSResult)

    @respx.mock
    def test_sync_propagates_exceptions(self) -> None:
        """Exceção async → exceção sync."""
        configure(cache_enabled=False)
        respx.get(url__startswith="https://api.fda.gov/drug/event.json").mock(
            side_effect=httpx.ConnectError("connection refused")
        )
        with pytest.raises((httpx.ConnectError, NetworkError)):
            faers.adverse_events("propofol", use_cache=False)
