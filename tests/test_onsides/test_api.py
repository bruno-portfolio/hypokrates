"""Testes para onsides/api.py — API pública."""

from __future__ import annotations

from pathlib import Path

import pytest

from hypokrates.onsides.api import onsides_check_event, onsides_events
from hypokrates.onsides.store import OnSIDESStore

GOLDEN_DIR = Path(__file__).parent.parent / "golden_data" / "onsides"


@pytest.fixture()
def store(tmp_path: Path) -> OnSIDESStore:
    """OnSIDESStore com golden data."""
    db_path = tmp_path / "test_onsides.duckdb"
    s = OnSIDESStore(db_path)
    s.load_from_csvs(str(GOLDEN_DIR))
    return s


class TestOnSIDESAPI:
    """Testes da API pública async."""

    async def test_onsides_events(self, store: OnSIDESStore) -> None:
        result = await onsides_events("propofol", _store=store)
        assert result.drug_name == "propofol"
        assert result.total_events > 0
        assert result.meta.source == "OnSIDES"
        names = [e.meddra_name for e in result.events]
        assert "Hypotension" in names

    async def test_onsides_events_min_confidence(self, store: OnSIDESStore) -> None:
        all_result = await onsides_events("propofol", min_confidence=0.0, _store=store)
        high_result = await onsides_events("propofol", min_confidence=0.9, _store=store)
        assert all_result.total_events >= high_result.total_events

    async def test_onsides_events_not_found(self, store: OnSIDESStore) -> None:
        result = await onsides_events("nonexistent_drug", _store=store)
        assert result.total_events == 0
        assert result.events == []

    async def test_onsides_check_event_found(self, store: OnSIDESStore) -> None:
        result = await onsides_check_event("propofol", "Bradycardia", _store=store)
        assert result is not None
        assert result.meddra_name == "Bradycardia"
        assert result.confidence > 0.8

    async def test_onsides_check_event_not_found(self, store: OnSIDESStore) -> None:
        result = await onsides_check_event("propofol", "Nonexistent Event", _store=store)
        assert result is None

    async def test_onsides_check_event_etomidate(self, store: OnSIDESStore) -> None:
        result = await onsides_check_event("Etomidate", "Adrenal insufficiency", _store=store)
        assert result is not None
        assert result.label_section == "BW"

    async def test_onsides_events_meta(self, store: OnSIDESStore) -> None:
        result = await onsides_events("propofol", _store=store)
        assert "OnSIDES" in result.meta.disclaimer
        assert result.meta.query["drug"] == "propofol"
