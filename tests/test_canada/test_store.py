"""Testes para canada/store.py — DuckDB store."""

from __future__ import annotations

from pathlib import Path

import pytest

from hypokrates.canada.store import CanadaVigilanceStore

GOLDEN_DIR = Path(__file__).parent.parent / "golden_data" / "canada"


@pytest.fixture()
def store(tmp_path: Path) -> CanadaVigilanceStore:
    """CanadaVigilanceStore em diretório temporário."""
    db_path = tmp_path / "test_canada.duckdb"
    return CanadaVigilanceStore(db_path)


@pytest.fixture()
def loaded_store(store: CanadaVigilanceStore) -> CanadaVigilanceStore:
    """Store com golden data carregada."""
    store.load_from_csvs(str(GOLDEN_DIR))
    return store


class TestCanadaVigilanceStore:
    """Testes do DuckDB store Canada Vigilance."""

    def test_empty_store_not_loaded(self, store: CanadaVigilanceStore) -> None:
        assert store.loaded is False

    def test_load_from_csvs(self, store: CanadaVigilanceStore) -> None:
        count = store.load_from_csvs(str(GOLDEN_DIR))
        assert count == 10
        assert store.loaded is True

    def test_count_reports(self, loaded_store: CanadaVigilanceStore) -> None:
        assert loaded_store.count_reports() == 10

    def test_count_drugs(self, loaded_store: CanadaVigilanceStore) -> None:
        assert loaded_store.count_drugs() == 10

    def test_count_reactions(self, loaded_store: CanadaVigilanceStore) -> None:
        assert loaded_store.count_reactions() == 10

    def test_four_counts_propofol_bradycardia(self, loaded_store: CanadaVigilanceStore) -> None:
        a, _b, _c, n = loaded_store.four_counts(["PROPOFOL"], ["BRADYCARDIA"])
        # Reports 1, 2 have propofol+bradycardia; report 9 has propofol(concomitant)+brady
        assert a >= 2
        assert n == 10

    def test_four_counts_suspect_only(self, loaded_store: CanadaVigilanceStore) -> None:
        a_all, _, _, _ = loaded_store.four_counts(["PROPOFOL"], ["BRADYCARDIA"])
        a_suspect, _, _, _ = loaded_store.four_counts(
            ["PROPOFOL"], ["BRADYCARDIA"], suspect_only=True
        )
        # suspect_only should exclude concomitant reports
        assert a_suspect <= a_all

    def test_four_counts_not_found(self, loaded_store: CanadaVigilanceStore) -> None:
        a, _b, _c, n = loaded_store.four_counts(["NONEXISTENT"], ["BRADYCARDIA"])
        assert a == 0
        assert n == 10

    def test_top_events(self, loaded_store: CanadaVigilanceStore) -> None:
        events = loaded_store.top_events(["PROPOFOL"], limit=5)
        assert len(events) > 0
        names = [e[0] for e in events]
        assert "Bradycardia" in names

    def test_top_events_not_found(self, loaded_store: CanadaVigilanceStore) -> None:
        events = loaded_store.top_events(["NONEXISTENT"])
        assert events == []

    def test_date_range(self, loaded_store: CanadaVigilanceStore) -> None:
        dr = loaded_store.date_range()
        assert "2020" in dr

    def test_reload_replaces_data(self, store: CanadaVigilanceStore) -> None:
        store.load_from_csvs(str(GOLDEN_DIR))
        assert store.loaded is True
        count = store.load_from_csvs(str(GOLDEN_DIR))
        assert count == 10

    def test_close(self, store: CanadaVigilanceStore) -> None:
        store.close()
