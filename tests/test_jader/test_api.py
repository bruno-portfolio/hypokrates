"""Testes para jader/api.py — API pública."""

from __future__ import annotations

from pathlib import Path

import pytest

from hypokrates.jader.api import jader_bulk_status, jader_signal, jader_top_events
from hypokrates.jader.store import JADERStore

GOLDEN_DIR = Path(__file__).parent.parent / "golden_data" / "jader"


@pytest.fixture()
def store(tmp_path: Path) -> JADERStore:
    """Store com golden data."""
    db_path = tmp_path / "test_jader.duckdb"
    s = JADERStore(db_path)
    s.load_from_csvs(str(GOLDEN_DIR))
    return s


class TestJADERAPI:
    """Testes da API pública async."""

    async def test_jader_signal(self, store: JADERStore) -> None:
        result = await jader_signal("PROPOFOL", "BRADYCARDIA", _store=store)
        assert result.drug == "PROPOFOL"
        assert result.event == "BRADYCARDIA"
        assert result.drug_event_count >= 2
        assert result.total_reports == 10
        assert result.meta.source == "JADER (PMDA)"

    async def test_jader_signal_not_found(self, store: JADERStore) -> None:
        result = await jader_signal("NONEXISTENT", "BRADYCARDIA", _store=store)
        assert result.drug_event_count == 0
        assert result.signal_detected is False
        assert result.prr == 0.0

    async def test_jader_top_events(self, store: JADERStore) -> None:
        events = await jader_top_events("PROPOFOL", limit=5, _store=store)
        assert len(events) > 0
        names = [e[0] for e in events]
        assert "BRADYCARDIA" in names

    async def test_jader_top_events_empty(self, store: JADERStore) -> None:
        events = await jader_top_events("NONEXISTENT", _store=store)
        assert events == []

    async def test_jader_bulk_status(self, store: JADERStore) -> None:
        status = await jader_bulk_status(_store=store)
        assert status.loaded is True
        assert status.total_reports == 10
        assert status.total_drugs == 10
        assert status.total_reactions == 10

    async def test_jader_signal_meta(self, store: JADERStore) -> None:
        result = await jader_signal("PROPOFOL", "BRADYCARDIA", _store=store)
        assert "JADER" in result.meta.disclaimer
        assert result.meta.query["drug"] == "PROPOFOL"

    async def test_jader_signal_confidence(self, store: JADERStore) -> None:
        result = await jader_signal("PROPOFOL", "BRADYCARDIA", _store=store)
        # Propofol and Bradycardia are in our mapping dicts → exact
        assert result.drug_confidence.value == "exact"
        assert result.event_confidence.value == "exact"

    async def test_jader_bulk_status_mapping_stats(self, store: JADERStore) -> None:
        status = await jader_bulk_status(_store=store)
        total_drugs = (
            status.exact_drug_mappings + status.inferred_drug_mappings + status.unmapped_drugs
        )
        assert total_drugs == status.total_drugs
