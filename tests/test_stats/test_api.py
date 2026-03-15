"""Testes para hypokrates.stats.api — integração com mock FAERS."""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, patch

import pytest

from hypokrates.config import configure
from hypokrates.stats.api import _aggregate_quarterly, signal, signal_timeline
from hypokrates.stats.models import QuarterlyCount, SignalResult, TimelineResult


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

    @patch("hypokrates.stats.api.FAERSClient")
    async def test_signal_suspect_only_adds_characterization_filter(
        self, mock_client_cls: Any
    ) -> None:
        """suspect_only=True adiciona drugcharacterization:1 nas queries com droga."""
        instance = mock_client_cls.return_value
        instance.fetch_total = _mock_fetch_total(
            {
                "drug_event": 50,
                "drug_total": 500,
                "event_total": 300,
                "n_total": 10000,
            }
        )
        instance.close = AsyncMock()

        await signal("propofol", "BRADYCARDIA", suspect_only=True)

        # Verificar que fetch_total foi chamado com drugcharacterization nas queries de droga
        calls = [str(c) for c in instance.fetch_total.call_args_list]
        drug_calls = [c for c in calls if "generic_name" in c]
        for c in drug_calls:
            assert "drugcharacterization" in c


class TestAggregateQuarterly:
    """Testes para _aggregate_quarterly()."""

    def test_basic_aggregation(self) -> None:
        """Contagens diárias agrupadas em trimestres."""
        daily = [
            {"time": "20230115", "count": 10},
            {"time": "20230220", "count": 5},
            {"time": "20230401", "count": 8},
            {"time": "20230715", "count": 12},
        ]
        result = _aggregate_quarterly(daily)
        assert len(result) == 3
        assert result[0] == QuarterlyCount(year=2023, quarter=1, count=15, label="2023-Q1")
        assert result[1] == QuarterlyCount(year=2023, quarter=2, count=8, label="2023-Q2")
        assert result[2] == QuarterlyCount(year=2023, quarter=3, count=12, label="2023-Q3")

    def test_empty_input(self) -> None:
        """Lista vazia retorna lista vazia."""
        assert _aggregate_quarterly([]) == []

    def test_short_time_string_skipped(self) -> None:
        """Strings de tempo curtas (< 6 chars) são ignoradas."""
        daily = [{"time": "2023", "count": 10}]
        assert _aggregate_quarterly(daily) == []

    def test_multiple_years(self) -> None:
        """Dados de anos diferentes são separados."""
        daily = [
            {"time": "20220101", "count": 5},
            {"time": "20230101", "count": 10},
        ]
        result = _aggregate_quarterly(daily)
        assert len(result) == 2
        assert result[0].year == 2022
        assert result[1].year == 2023


class TestSignalTimeline:
    """Testes para signal_timeline()."""

    @pytest.fixture(autouse=True)
    def _disable_cache(self) -> None:
        configure(cache_enabled=False)

    @patch("hypokrates.stats.api.FAERSClient")
    async def test_timeline_basic(self, mock_client_cls: Any) -> None:
        """Timeline retorna quarters com estatísticas."""
        instance = mock_client_cls.return_value
        instance.fetch_count = AsyncMock(
            return_value={
                "results": [
                    {"time": "20230115", "count": 10},
                    {"time": "20230220", "count": 5},
                    {"time": "20230401", "count": 8},
                    {"time": "20230715", "count": 20},
                ]
            }
        )
        instance.fetch_total = _mock_fetch_total({"drug_total": 100})
        instance.close = AsyncMock()

        result = await signal_timeline("propofol", "bradycardia")

        assert isinstance(result, TimelineResult)
        assert result.drug == "propofol"
        assert result.event == "bradycardia"
        assert result.total_reports == 43
        assert len(result.quarters) == 3
        assert result.peak_quarter is not None
        assert result.peak_quarter.count == 20

    @patch("hypokrates.stats.api.FAERSClient")
    async def test_timeline_spike_detection(self, mock_client_cls: Any) -> None:
        """Quarters com count > mean+2*std são flagados como spikes."""
        instance = mock_client_cls.return_value
        # 8 quarters normais (~1 cada), 1 spike (100) — spike claro
        instance.fetch_count = AsyncMock(
            return_value={
                "results": [
                    {"time": "20210115", "count": 1},
                    {"time": "20210415", "count": 1},
                    {"time": "20210715", "count": 1},
                    {"time": "20211015", "count": 1},
                    {"time": "20220115", "count": 1},
                    {"time": "20220415", "count": 1},
                    {"time": "20220715", "count": 1},
                    {"time": "20221015", "count": 1},
                    {"time": "20230115", "count": 100},
                ]
            }
        )
        instance.fetch_total = _mock_fetch_total({"drug_total": 100})
        instance.close = AsyncMock()

        result = await signal_timeline("drug", "event")

        assert len(result.spike_quarters) == 1
        assert result.spike_quarters[0].year == 2023
        assert result.spike_quarters[0].count == 100

    @patch("hypokrates.stats.api.FAERSClient")
    async def test_timeline_empty(self, mock_client_cls: Any) -> None:
        """Sem resultados retorna timeline vazia."""
        instance = mock_client_cls.return_value
        instance.fetch_count = AsyncMock(return_value={"results": []})
        instance.fetch_total = _mock_fetch_total({"drug_total": 100})
        instance.close = AsyncMock()

        result = await signal_timeline("drug", "event")

        assert result.total_reports == 0
        assert result.quarters == []
        assert result.peak_quarter is None
        assert result.spike_quarters == []

    @patch("hypokrates.stats.api.FAERSClient")
    async def test_timeline_suspect_only(self, mock_client_cls: Any) -> None:
        """suspect_only adiciona characterization filter na search."""
        instance = mock_client_cls.return_value
        instance.fetch_count = AsyncMock(return_value={"results": []})
        instance.fetch_total = _mock_fetch_total({"drug_total": 100})
        instance.close = AsyncMock()

        result = await signal_timeline("drug", "event", suspect_only=True)

        assert result.suspect_only is True
        # Verificar que fetch_count foi chamado com drugcharacterization
        search_arg = instance.fetch_count.call_args[0][0]
        assert "drugcharacterization" in search_arg
