"""Testes para jader/store.py — DuckDB store."""

from __future__ import annotations

from pathlib import Path

import pytest

from hypokrates.jader.store import JADERStore

GOLDEN_DIR = Path(__file__).parent.parent / "golden_data" / "jader"


@pytest.fixture()
def store(tmp_path: Path) -> JADERStore:
    """JADERStore em diretório temporário."""
    db_path = tmp_path / "test_jader.duckdb"
    return JADERStore(db_path)


@pytest.fixture()
def loaded_store(store: JADERStore) -> JADERStore:
    """Store com golden data carregada."""
    store.load_from_csvs(str(GOLDEN_DIR))
    return store


class TestJADERStore:
    """Testes do DuckDB store JADER."""

    def test_empty_store_not_loaded(self, store: JADERStore) -> None:
        assert store.loaded is False

    def test_load_from_csvs(self, store: JADERStore) -> None:
        count = store.load_from_csvs(str(GOLDEN_DIR))
        assert count == 10
        assert store.loaded is True

    def test_count_reports(self, loaded_store: JADERStore) -> None:
        assert loaded_store.count_reports() == 10

    def test_count_drugs(self, loaded_store: JADERStore) -> None:
        assert loaded_store.count_drugs() == 10

    def test_count_reactions(self, loaded_store: JADERStore) -> None:
        assert loaded_store.count_reactions() == 10

    def test_four_counts_propofol_bradycardia(self, loaded_store: JADERStore) -> None:
        a, _b, _c, n = loaded_store.four_counts(["PROPOFOL"], ["BRADYCARDIA"])
        # J-001 and J-002 have propofol(suspect)+bradycardia
        # J-009 has propofol(concomitant)+bradycardia
        assert a >= 2
        assert n == 10

    def test_four_counts_suspect_only(self, loaded_store: JADERStore) -> None:
        a_all, _, _, _ = loaded_store.four_counts(["PROPOFOL"], ["BRADYCARDIA"])
        a_suspect, _, _, _ = loaded_store.four_counts(
            ["PROPOFOL"], ["BRADYCARDIA"], suspect_only=True
        )
        assert a_suspect <= a_all

    def test_four_counts_not_found(self, loaded_store: JADERStore) -> None:
        a, _b, _c, n = loaded_store.four_counts(["NONEXISTENT"], ["BRADYCARDIA"])
        assert a == 0
        assert n == 10

    def test_top_events(self, loaded_store: JADERStore) -> None:
        events = loaded_store.top_events(["PROPOFOL"], limit=5)
        assert len(events) > 0
        names = [e[0] for e in events]
        assert "BRADYCARDIA" in names

    def test_top_events_not_found(self, loaded_store: JADERStore) -> None:
        events = loaded_store.top_events(["NONEXISTENT"])
        assert events == []

    def test_date_range(self, loaded_store: JADERStore) -> None:
        dr = loaded_store.date_range()
        assert "J-001" in dr or "J-010" in dr

    def test_mapping_stats(self, loaded_store: JADERStore) -> None:
        stats = loaded_store.mapping_stats()
        assert stats["exact_drugs"] > 0
        assert stats["exact_events"] > 0

    def test_reload_replaces_data(self, store: JADERStore) -> None:
        store.load_from_csvs(str(GOLDEN_DIR))
        assert store.loaded is True
        count = store.load_from_csvs(str(GOLDEN_DIR))
        assert count == 10

    def test_close(self, store: JADERStore) -> None:
        store.close()
