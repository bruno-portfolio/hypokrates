"""Testes para onsides/store.py — DuckDB store."""

from __future__ import annotations

from pathlib import Path

import pytest

from hypokrates.onsides.store import OnSIDESStore

GOLDEN_DIR = Path(__file__).parent.parent / "golden_data" / "onsides"


@pytest.fixture()
def store(tmp_path: Path) -> OnSIDESStore:
    """OnSIDESStore em diretório temporário."""
    db_path = tmp_path / "test_onsides.duckdb"
    s = OnSIDESStore(db_path)
    return s


@pytest.fixture()
def loaded_store(store: OnSIDESStore) -> OnSIDESStore:
    """OnSIDESStore com golden data carregada."""
    store.load_from_csvs(str(GOLDEN_DIR))
    return store


class TestOnSIDESStore:
    """Testes do DuckDB store OnSIDES."""

    def test_empty_store_not_loaded(self, store: OnSIDESStore) -> None:
        assert store.loaded is False

    def test_load_from_csvs(self, store: OnSIDESStore) -> None:
        count = store.load_from_csvs(str(GOLDEN_DIR))
        assert count == 6  # 6 labels no golden data
        assert store.loaded is True

    def test_query_events_propofol(self, loaded_store: OnSIDESStore) -> None:
        events = loaded_store.query_events("Propofol")
        assert len(events) > 0
        names = [e.meddra_name for e in events]
        assert "Hypotension" in names
        assert "Bradycardia" in names

    def test_query_events_case_insensitive(self, loaded_store: OnSIDESStore) -> None:
        events = loaded_store.query_events("propofol")
        assert len(events) > 0

    def test_query_events_min_confidence(self, loaded_store: OnSIDESStore) -> None:
        all_events = loaded_store.query_events("propofol", min_confidence=0.0)
        high_events = loaded_store.query_events("propofol", min_confidence=0.9)
        assert len(all_events) >= len(high_events)

    def test_query_events_sorted_by_confidence(self, loaded_store: OnSIDESStore) -> None:
        events = loaded_store.query_events("propofol", min_confidence=0.0)
        confidences = [e.confidence for e in events]
        assert confidences == sorted(confidences, reverse=True)

    def test_query_events_sources(self, loaded_store: OnSIDESStore) -> None:
        events = loaded_store.query_events("propofol")
        # Bradycardia is in US, EU, UK, JP labels
        brady = [e for e in events if e.meddra_name == "Bradycardia"]
        assert len(brady) > 0
        assert "US" in brady[0].sources
        assert brady[0].num_sources >= 3

    def test_query_events_hypotension_multi_source(self, loaded_store: OnSIDESStore) -> None:
        events = loaded_store.query_events("propofol")
        hypo = [e for e in events if e.meddra_name == "Hypotension"]
        assert len(hypo) > 0
        assert hypo[0].num_sources >= 3

    def test_query_events_not_found(self, loaded_store: OnSIDESStore) -> None:
        events = loaded_store.query_events("nonexistent_drug_xyz")
        assert events == []

    def test_check_event_found(self, loaded_store: OnSIDESStore) -> None:
        result = loaded_store.check_event("propofol", "Bradycardia")
        assert result is not None
        assert result.meddra_name == "Bradycardia"
        assert result.confidence > 0.8
        assert "US" in result.sources

    def test_check_event_not_found(self, loaded_store: OnSIDESStore) -> None:
        result = loaded_store.check_event("propofol", "Nonexistent Event")
        assert result is None

    def test_check_event_different_drug(self, loaded_store: OnSIDESStore) -> None:
        result = loaded_store.check_event("Etomidate", "Adrenal insufficiency")
        assert result is not None
        assert result.label_section == "BW"  # Boxed Warning

    def test_reload_replaces_data(self, store: OnSIDESStore) -> None:
        store.load_from_csvs(str(GOLDEN_DIR))
        assert store.loaded is True
        count = store.load_from_csvs(str(GOLDEN_DIR))
        assert count == 6

    def test_close(self, store: OnSIDESStore) -> None:
        store.close()
        # After close, operations should fail gracefully
