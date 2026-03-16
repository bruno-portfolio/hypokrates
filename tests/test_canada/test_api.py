"""Testes para canada/api.py — API pública."""

from __future__ import annotations

from pathlib import Path

import pytest

from hypokrates.canada.api import canada_bulk_status, canada_signal, canada_top_events
from hypokrates.canada.store import CanadaVigilanceStore

GOLDEN_DIR = Path(__file__).parent.parent / "golden_data" / "canada"


@pytest.fixture()
def store(tmp_path: Path) -> CanadaVigilanceStore:
    """Store com golden data."""
    db_path = tmp_path / "test_canada.duckdb"
    s = CanadaVigilanceStore(db_path)
    s.load_from_csvs(str(GOLDEN_DIR))
    return s


class TestCanadaAPI:
    """Testes da API pública async."""

    async def test_canada_signal(self, store: CanadaVigilanceStore) -> None:
        result = await canada_signal("PROPOFOL", "Bradycardia", _store=store)
        assert result.drug == "PROPOFOL"
        assert result.event == "Bradycardia"
        assert result.drug_event_count >= 2
        assert result.total_reports == 10
        assert result.meta.source == "Canada Vigilance"

    async def test_canada_signal_not_found(self, store: CanadaVigilanceStore) -> None:
        result = await canada_signal("NONEXISTENT", "Bradycardia", _store=store)
        assert result.drug_event_count == 0
        assert result.signal_detected is False
        assert result.prr == 0.0

    async def test_canada_top_events(self, store: CanadaVigilanceStore) -> None:
        events = await canada_top_events("PROPOFOL", limit=5, _store=store)
        assert len(events) > 0
        names = [e[0] for e in events]
        assert "Bradycardia" in names

    async def test_canada_top_events_empty(self, store: CanadaVigilanceStore) -> None:
        events = await canada_top_events("NONEXISTENT", _store=store)
        assert events == []

    async def test_canada_bulk_status(self, store: CanadaVigilanceStore) -> None:
        status = await canada_bulk_status(_store=store)
        assert status.loaded is True
        assert status.total_reports == 10
        assert status.total_drugs == 10
        assert status.total_reactions == 10
        assert "2020" in status.date_range

    async def test_canada_signal_meta(self, store: CanadaVigilanceStore) -> None:
        result = await canada_signal("PROPOFOL", "Bradycardia", _store=store)
        assert "Canada Vigilance" in result.meta.disclaimer
        assert result.meta.query["drug"] == "PROPOFOL"
