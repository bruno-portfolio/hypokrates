"""Testes para hypokrates.stats.api — integração com mock FAERS."""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, patch

import pytest

from hypokrates.config import configure
from hypokrates.stats.api import signal
from hypokrates.stats.models import SignalResult


def _mock_fetch_total(totals: dict[str, int]) -> AsyncMock:
    """Cria mock para FAERSClient.fetch_total baseado na search string."""

    async def _side_effect(search: str, *, use_cache: bool = True) -> int:
        if search == "":
            return totals.get("n_total", 10000)
        if " AND " in search:
            return totals.get("drug_event", 100)
        if "generic_name" in search:
            return totals.get("drug_total", 1000)
        if "reactionmeddrapt" in search:
            return totals.get("event_total", 300)
        return 0

    return AsyncMock(side_effect=_side_effect)


class TestSignalAPI:
    """Testes para signal() — usa mock do FAERSClient."""

    @pytest.fixture(autouse=True)
    def _disable_cache(self) -> None:
        configure(cache_enabled=False)

    @patch("hypokrates.stats.api.FAERSClient")
    async def test_signal_returns_result(self, mock_client_cls: Any) -> None:
        """Mock FAERS → SignalResult completo."""
        instance = mock_client_cls.return_value
        instance.fetch_total = _mock_fetch_total(
            {
                "drug_event": 100,
                "drug_total": 1000,
                "event_total": 300,
                "n_total": 10000,
            }
        )
        instance.close = AsyncMock()

        result = await signal("propofol", "PRIS")
        assert isinstance(result, SignalResult)
        assert result.drug == "propofol"
        assert result.event == "PRIS"
        assert result.table.a == 100
        assert result.table.n == 10000
        assert result.signal_detected is True

    @patch("hypokrates.stats.api.FAERSClient")
    async def test_signal_below_min_count(self, mock_client_cls: Any) -> None:
        """a < 3 → signal_detected=False independente das medidas."""
        instance = mock_client_cls.return_value
        instance.fetch_total = _mock_fetch_total(
            {
                "drug_event": 2,
                "drug_total": 1000,
                "event_total": 300,
                "n_total": 10000,
            }
        )
        instance.close = AsyncMock()

        result = await signal("raredrug", "RAREREACTION")
        assert result.signal_detected is False
        assert result.table.a == 2

    @patch("hypokrates.stats.api.FAERSClient")
    async def test_signal_zero_counts(self, mock_client_cls: Any) -> None:
        """drug_event=0 → tudo zero, sem crash."""
        instance = mock_client_cls.return_value
        instance.fetch_total = _mock_fetch_total(
            {
                "drug_event": 0,
                "drug_total": 1000,
                "event_total": 300,
                "n_total": 10000,
            }
        )
        instance.close = AsyncMock()

        result = await signal("nodrug", "NOEVENT")
        assert result.signal_detected is False
        assert result.prr.value == 0.0

    @patch("hypokrates.stats.api.FAERSClient")
    async def test_signal_meta_complete(self, mock_client_cls: Any) -> None:
        """MetaInfo tem todos os campos."""
        instance = mock_client_cls.return_value
        instance.fetch_total = _mock_fetch_total(
            {
                "drug_event": 100,
                "drug_total": 1000,
                "event_total": 300,
                "n_total": 10000,
            }
        )
        instance.close = AsyncMock()

        result = await signal("propofol", "DEATH")
        assert result.meta.source == "OpenFDA/FAERS"
        assert result.meta.query["drug"] == "propofol"
        assert result.meta.query["event"] == "DEATH"
        assert result.meta.total_results == 100
        assert result.meta.retrieved_at is not None
        assert result.meta.disclaimer

    @patch("hypokrates.stats.api.FAERSClient")
    async def test_signal_not_significant(self, mock_client_cls: Any) -> None:
        """Tabela balanceada → nenhuma medida significante."""
        instance = mock_client_cls.return_value
        instance.fetch_total = _mock_fetch_total(
            {
                "drug_event": 100,
                "drug_total": 1000,
                "event_total": 1000,
                "n_total": 10000,
            }
        )
        instance.close = AsyncMock()

        result = await signal("aspirin", "HEADACHE")
        assert result.signal_detected is False

    @patch("hypokrates.stats.api.FAERSClient")
    async def test_signal_calls_close(self, mock_client_cls: Any) -> None:
        """Client é fechado após uso."""
        instance = mock_client_cls.return_value
        instance.fetch_total = _mock_fetch_total(
            {
                "drug_event": 100,
                "drug_total": 1000,
                "event_total": 300,
                "n_total": 10000,
            }
        )
        instance.close = AsyncMock()

        await signal("propofol", "PRIS")
        instance.close.assert_called_once()
