"""Testes para jader/parser.py."""

from __future__ import annotations

from pathlib import Path

import pytest

from hypokrates.jader.parser import _find_jader_file, load_files_to_store
from hypokrates.jader.store import JADERStore

GOLDEN_DIR = Path(__file__).parent.parent / "golden_data" / "jader"


@pytest.fixture()
def store(tmp_path: Path) -> JADERStore:
    """JADERStore em diretório temporário."""
    db_path = tmp_path / "test_jader.duckdb"
    return JADERStore(db_path)


class TestJADERParser:
    """Testes do parser de CSVs JADER."""

    def test_find_jader_file_exact(self) -> None:
        result = _find_jader_file(GOLDEN_DIR, "demo")
        assert result is not None
        assert "demo" in result.name

    def test_find_jader_file_not_found(self, tmp_path: Path) -> None:
        result = _find_jader_file(tmp_path, "nonexistent")
        assert result is None

    def test_load_files_to_store(self, store: JADERStore) -> None:
        count = load_files_to_store(store, str(GOLDEN_DIR))
        assert count == 10

    def test_load_translates_drugs(self, store: JADERStore) -> None:
        load_files_to_store(store, str(GOLDEN_DIR))
        rows = store.query_in_lock(
            "SELECT DISTINCT drug_name_en FROM jader_drug WHERE drug_name_en != ''"
        )
        names = {r[0] for r in rows}
        assert "PROPOFOL" in names
        assert "FENTANYL" in names

    def test_load_translates_events(self, store: JADERStore) -> None:
        load_files_to_store(store, str(GOLDEN_DIR))
        rows = store.query_in_lock("SELECT DISTINCT pt_en FROM jader_reac WHERE pt_en != ''")
        names = {r[0] for r in rows}
        assert "BRADYCARDIA" in names
        assert "NAUSEA" in names

    def test_dedup_builds(self, store: JADERStore) -> None:
        load_files_to_store(store, str(GOLDEN_DIR))
        rows = store.query_in_lock("SELECT COUNT(*) FROM jader_dedup")
        assert rows[0][0] == 10

    def test_drug_confidence_stored(self, store: JADERStore) -> None:
        load_files_to_store(store, str(GOLDEN_DIR))
        rows = store.query_in_lock(
            "SELECT drug_confidence FROM jader_drug WHERE drug_name_en = 'PROPOFOL'"
        )
        assert len(rows) > 0
        assert rows[0][0] == "exact"
