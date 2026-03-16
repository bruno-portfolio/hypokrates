"""Testes para hypokrates.stats.api — integração com mock FAERS."""

from __future__ import annotations

from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock, patch

import pytest

from hypokrates.config import configure
from hypokrates.faers_bulk.drug_resolver import clear_cache as clear_resolver_cache
from hypokrates.faers_bulk.store import FAERSBulkStore
from hypokrates.stats.api import (
    _aggregate_quarterly,
    _build_reaction_query,
    signal,
    signal_timeline,
)
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


class TestBuildReactionQuery:
    """Testes para _build_reaction_query()."""

    def test_single_unknown_term(self) -> None:
        """Termo desconhecido gera query simples."""
        result = _build_reaction_query("HEADACHE", "patient.reaction.reactionmeddrapt.exact")
        assert result == 'patient.reaction.reactionmeddrapt.exact:"HEADACHE"'

    def test_alias_term(self) -> None:
        """Alias agora expande para grupo completo (canonical + aliases)."""
        result = _build_reaction_query(
            "ELECTROCARDIOGRAM QT PROLONGED", "patient.reaction.reactionmeddrapt.exact"
        )
        assert result.startswith("(")
        assert result.endswith(")")
        assert "QT PROLONGATION" in result
        assert "ELECTROCARDIOGRAM QT PROLONGED" in result
        assert "TORSADE DE POINTES" in result

    def test_canonical_term_expands(self) -> None:
        """Canonical expande para OR query com todos os aliases."""
        result = _build_reaction_query(
            "QT PROLONGATION", "patient.reaction.reactionmeddrapt.exact"
        )
        assert result.startswith("(")
        assert result.endswith(")")
        assert "QT PROLONGATION" in result
        assert "ELECTROCARDIOGRAM QT PROLONGED" in result
        assert "LONG QT SYNDROME" in result
        assert "TORSADE DE POINTES" in result
        # Espaço = OR no OpenFDA (não +, que seria AND)
        assert "+" not in result
        assert '" ' in result

    def test_case_insensitive(self) -> None:
        """Input case-insensitive é normalizado."""
        result = _build_reaction_query(
            "qt prolongation", "patient.reaction.reactionmeddrapt.exact"
        )
        assert "QT PROLONGATION" in result
        assert "ELECTROCARDIOGRAM QT PROLONGED" in result


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


GOLDEN_ZIP_Q3 = (
    Path(__file__).parent.parent / "golden_data" / "faers_bulk" / "faers_ascii_2024Q3.zip"
)


class TestSignalBulkMode:
    """Testes para signal() com FAERS Bulk (dual-mode)."""

    @pytest.fixture(autouse=True)
    def _setup(self, tmp_path: Path) -> None:
        """Setup: cria store singleton com golden data."""
        configure(cache_enabled=False)
        db_path = tmp_path / "test_signal_bulk.duckdb"
        store = FAERSBulkStore(db_path)
        store.load_quarter(GOLDEN_ZIP_Q3)
        FAERSBulkStore._instance = store
        clear_resolver_cache()
        yield  # type: ignore[misc]
        FAERSBulkStore._instance = None

    async def test_signal_use_bulk_true(self) -> None:
        """use_bulk=True força uso do bulk store."""
        result = await signal("propofol", "bradycardia", use_bulk=True)
        assert isinstance(result, SignalResult)
        assert result.meta.source == "FAERS/bulk (deduplicated)"
        assert result.drug == "propofol"
        assert result.event == "bradycardia"

    @patch(
        "hypokrates.faers_bulk.api.is_bulk_available", new_callable=AsyncMock, return_value=True
    )
    async def test_signal_use_bulk_auto_detects(self, _mock_avail: AsyncMock) -> None:
        """use_bulk=None auto-detecta bulk disponível."""
        result = await signal("propofol", "bradycardia", use_bulk=None)
        assert result.meta.source == "FAERS/bulk (deduplicated)"

    @patch("hypokrates.stats.api.FAERSClient")
    async def test_signal_use_bulk_false_forces_api(self, mock_client_cls: Any) -> None:
        """use_bulk=False força uso da API, mesmo com bulk disponível."""
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

        result = await signal("propofol", "DEATH", use_bulk=False)
        assert result.meta.source == "OpenFDA/FAERS"

    async def test_signal_bulk_primary_suspect_only(self) -> None:
        """primary_suspect_only=True usa PS_ONLY no bulk."""
        result = await signal("propofol", "bradycardia", primary_suspect_only=True, use_bulk=True)
        assert result.meta.source == "FAERS/bulk (deduplicated)"
        assert result.meta.query["role_filter"] == "ps_only"

    async def test_signal_bulk_suspect_only(self) -> None:
        """suspect_only=True usa SUSPECT filter no bulk."""
        result = await signal("propofol", "bradycardia", suspect_only=True, use_bulk=True)
        assert result.meta.query["role_filter"] == "suspect"

    async def test_signal_bulk_default_is_all(self) -> None:
        """Sem suspect flags usa ALL no bulk."""
        result = await signal("propofol", "bradycardia", use_bulk=True)
        assert result.meta.query["role_filter"] == "all"

    async def test_signal_bulk_counts_differ_from_api_path(self) -> None:
        """Verifica que bulk retorna contagens do golden data."""
        result = await signal("propofol", "bradycardia", use_bulk=True)
        # ALL role: a=3 (PROPOFOL em qualquer role + BRADYCARDIA)
        assert result.table.a == 3


class TestSignalPrimarySuspectOnly:
    """Testes para primary_suspect_only no API path."""

    @pytest.fixture(autouse=True)
    def _disable_cache(self) -> None:
        configure(cache_enabled=False)

    @patch("hypokrates.stats.api.FAERSClient")
    async def test_primary_suspect_only_falls_back_to_suspect_only(
        self, mock_client_cls: Any
    ) -> None:
        """primary_suspect_only=True sem bulk → warning + fallback to suspect_only."""
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

        result = await signal(
            "propofol",
            "BRADYCARDIA",
            primary_suspect_only=True,
            use_bulk=False,
        )

        assert isinstance(result, SignalResult)
        # Deve ter usado suspect_only (drugcharacterization na query)
        calls = [str(c) for c in instance.fetch_total.call_args_list]
        drug_calls = [c for c in calls if "generic_name" in c]
        for c in drug_calls:
            assert "drugcharacterization" in c


class TestSignalTimelineBulkMode:
    """Testes para signal_timeline() com FAERS Bulk."""

    @pytest.fixture(autouse=True)
    def _setup(self, tmp_path: Path) -> None:
        """Setup: cria store singleton com golden data."""
        configure(cache_enabled=False)
        db_path = tmp_path / "test_timeline_bulk.duckdb"
        store = FAERSBulkStore(db_path)
        store.load_quarter(GOLDEN_ZIP_Q3)
        FAERSBulkStore._instance = store
        clear_resolver_cache()
        yield  # type: ignore[misc]
        FAERSBulkStore._instance = None

    @patch(
        "hypokrates.faers_bulk.api.is_bulk_available", new_callable=AsyncMock, return_value=True
    )
    async def test_signal_timeline_uses_bulk_when_available(self, _mock_avail: AsyncMock) -> None:
        """signal_timeline com use_bulk=None auto-detecta bulk e usa."""
        result = await signal_timeline("propofol", "bradycardia", use_bulk=None)
        assert isinstance(result, TimelineResult)
        assert result.meta.source == "FAERS/bulk (deduplicated)"

    async def test_signal_timeline_bulk_explicit(self) -> None:
        """signal_timeline com use_bulk=True usa bulk."""
        result = await signal_timeline("propofol", "bradycardia", use_bulk=True)
        assert result.meta.source == "FAERS/bulk (deduplicated)"

    @patch("hypokrates.stats.api.FAERSClient")
    async def test_signal_timeline_fetch_count_failure(self, mock_client_cls: Any) -> None:
        """Quando fetch_count falha, retorna timeline vazia."""
        instance = mock_client_cls.return_value
        instance.fetch_count = AsyncMock(side_effect=RuntimeError("FAERS down"))
        instance.fetch_total = _mock_fetch_total({"drug_total": 100})
        instance.close = AsyncMock()

        result = await signal_timeline("propofol", "bradycardia", use_bulk=False)

        assert result.total_reports == 0
        assert result.quarters == []
