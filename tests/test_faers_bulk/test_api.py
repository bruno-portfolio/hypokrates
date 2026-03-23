"""Testes para faers_bulk/api.py — API async."""

from __future__ import annotations

from pathlib import Path

import pytest

from hypokrates.faers_bulk.api import (
    bulk_drug_total,
    bulk_signal,
    bulk_store_status,
    bulk_top_events,
    is_bulk_available,
)
from hypokrates.faers_bulk.constants import RoleCodFilter
from hypokrates.faers_bulk.drug_resolver import clear_cache
from hypokrates.faers_bulk.store import FAERSBulkStore
from hypokrates.stats.models import SignalResult

GOLDEN_ZIP_Q3 = (
    Path(__file__).parent.parent / "golden_data" / "faers_bulk" / "faers_ascii_2024Q3.zip"
)


@pytest.fixture()
def loaded_store(tmp_path: Path) -> FAERSBulkStore:
    """FAERSBulkStore com Q3 carregado — registrado como singleton."""
    db_path = tmp_path / "test_api.duckdb"
    store = FAERSBulkStore(db_path)
    store.load_quarter(GOLDEN_ZIP_Q3)
    # Registrar como singleton para que api.py use via get_instance()
    FAERSBulkStore._instance = store
    clear_cache()
    yield store  # type: ignore[misc]
    FAERSBulkStore._instance = None


@pytest.fixture()
def empty_store(tmp_path: Path) -> FAERSBulkStore:
    """FAERSBulkStore vazio — registrado como singleton."""
    db_path = tmp_path / "test_api_empty.duckdb"
    store = FAERSBulkStore(db_path)
    FAERSBulkStore._instance = store
    yield store  # type: ignore[misc]
    FAERSBulkStore._instance = None


class TestIsAvailable:
    """Testes para is_bulk_available()."""

    async def test_available_when_loaded(self, loaded_store: FAERSBulkStore) -> None:
        assert await is_bulk_available() is True

    async def test_not_available_when_empty(self, empty_store: FAERSBulkStore) -> None:
        assert await is_bulk_available() is False


class TestBulkSignal:
    """Testes para bulk_signal()."""

    async def test_basic_signal(self, loaded_store: FAERSBulkStore) -> None:
        """bulk_signal retorna SignalResult válido (default SUSPECT)."""
        result = await bulk_signal("propofol", "bradycardia")
        assert isinstance(result, SignalResult)
        assert result.drug == "propofol"
        assert result.event == "bradycardia"
        assert result.table.a == 2  # default SUSPECT (PS+SS)

    async def test_signal_suspect_filter(self, loaded_store: FAERSBulkStore) -> None:
        """SUSPECT filter: PS + SS."""
        result = await bulk_signal("propofol", "bradycardia", role_filter=RoleCodFilter.SUSPECT)
        assert result.table.a == 2

    async def test_signal_ps_only(self, loaded_store: FAERSBulkStore) -> None:
        result = await bulk_signal("propofol", "bradycardia", role_filter=RoleCodFilter.PS_ONLY)
        assert result.table.a == 1

    async def test_meta_source(self, loaded_store: FAERSBulkStore) -> None:
        result = await bulk_signal("propofol", "bradycardia")
        assert result.meta.source == "FAERS/bulk (deduplicated)"

    async def test_signal_detected(self, loaded_store: FAERSBulkStore) -> None:
        result = await bulk_signal("propofol", "bradycardia")
        # Com golden data pequeno, pode ou não ser detectado
        assert isinstance(result.signal_detected, bool)

    async def test_nonexistent_drug(self, loaded_store: FAERSBulkStore) -> None:
        result = await bulk_signal("NONEXISTENT", "BRADYCARDIA")
        assert result.table.a == 0


class TestBulkTopEvents:
    """Testes para bulk_top_events()."""

    async def test_basic_top_events(self, loaded_store: FAERSBulkStore) -> None:
        """Retorna lista de (event, count)."""
        events = await bulk_top_events("propofol")
        assert len(events) > 0
        assert all(isinstance(e, tuple) for e in events)
        event_names = [e[0] for e in events]
        assert "BRADYCARDIA" in event_names

    async def test_top_events_ps_only(self, loaded_store: FAERSBulkStore) -> None:
        """PS_ONLY filter retorna resultados."""
        events = await bulk_top_events("propofol", role_filter=RoleCodFilter.PS_ONLY)
        assert isinstance(events, list)

    async def test_top_events_limit(self, loaded_store: FAERSBulkStore) -> None:
        """Limit clamps resultado."""
        events = await bulk_top_events("propofol", limit=1)
        assert len(events) <= 1


class TestBulkDrugTotal:
    """Testes para bulk_drug_total()."""

    async def test_propofol_suspect(self, loaded_store: FAERSBulkStore) -> None:
        """PROPOFOL SUSPECT: 3 cases dedup."""
        total = await bulk_drug_total("propofol")
        assert total == 3

    async def test_propofol_ps_only(self, loaded_store: FAERSBulkStore) -> None:
        """PROPOFOL PS_ONLY: 2 cases dedup."""
        total = await bulk_drug_total("propofol", role_filter=RoleCodFilter.PS_ONLY)
        assert total == 2


class TestBulkStoreStatus:
    """Testes para bulk_store_status()."""

    async def test_status_loaded(self, loaded_store: FAERSBulkStore) -> None:
        status = await bulk_store_status()
        assert status.total_reports == 9
        assert status.deduped_cases == 5
        assert len(status.quarters_loaded) == 1
