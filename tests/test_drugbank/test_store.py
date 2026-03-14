"""Testes para drugbank/store.py — DuckDB store."""

from __future__ import annotations

from pathlib import Path

import pytest

from hypokrates.drugbank.store import DrugBankStore

GOLDEN_XML = Path(__file__).parent.parent / "golden_data" / "drugbank" / "sample_drugbank.xml"


@pytest.fixture()
def store(tmp_path: Path) -> DrugBankStore:
    """DrugBankStore em diretório temporário."""
    db_path = tmp_path / "test_drugbank.duckdb"
    s = DrugBankStore(db_path)
    return s


class TestDrugBankStore:
    """Testes do DuckDB store."""

    def test_empty_store_not_loaded(self, store: DrugBankStore) -> None:
        assert store.loaded is False

    def test_load_from_xml(self, store: DrugBankStore) -> None:
        count = store.load_from_xml(str(GOLDEN_XML))
        assert count == 3
        assert store.loaded is True

    def test_find_drug_by_name(self, store: DrugBankStore) -> None:
        store.load_from_xml(str(GOLDEN_XML))
        info = store.find_drug("Propofol")
        assert info is not None
        assert info.drugbank_id == "DB00818"

    def test_find_drug_case_insensitive(self, store: DrugBankStore) -> None:
        store.load_from_xml(str(GOLDEN_XML))
        info = store.find_drug("propofol")
        assert info is not None
        assert info.name == "Propofol"

    def test_find_drug_by_synonym(self, store: DrugBankStore) -> None:
        store.load_from_xml(str(GOLDEN_XML))
        info = store.find_drug("Diprivan")
        assert info is not None
        assert info.name == "Propofol"

    def test_find_drug_not_found(self, store: DrugBankStore) -> None:
        store.load_from_xml(str(GOLDEN_XML))
        info = store.find_drug("nonexistent")
        assert info is None

    def test_get_drug_by_id(self, store: DrugBankStore) -> None:
        store.load_from_xml(str(GOLDEN_XML))
        info = store.get_drug("DB00818")
        assert info is not None
        assert info.name == "Propofol"
        assert len(info.targets) == 1
        assert len(info.enzymes) == 2

    def test_find_interactions(self, store: DrugBankStore) -> None:
        store.load_from_xml(str(GOLDEN_XML))
        interactions = store.find_interactions("propofol")
        assert len(interactions) == 2
        partner_names = [i.partner_name for i in interactions]
        assert "Fentanyl" in partner_names

    def test_find_interactions_not_found(self, store: DrugBankStore) -> None:
        store.load_from_xml(str(GOLDEN_XML))
        interactions = store.find_interactions("nonexistent")
        assert interactions == []

    def test_reload_replaces_data(self, store: DrugBankStore) -> None:
        store.load_from_xml(str(GOLDEN_XML))
        assert store.loaded is True
        count = store.load_from_xml(str(GOLDEN_XML))
        assert count == 3

    def test_singleton_reset(self, tmp_path: Path) -> None:
        DrugBankStore.reset()
        assert DrugBankStore._instance is None

    def test_close(self, store: DrugBankStore) -> None:
        store.close()
        # Should not raise
