"""Testes para drugbank/api.py — API pública."""

from __future__ import annotations

from pathlib import Path

import pytest

from hypokrates.drugbank.api import drug_info, drug_interactions, drug_mechanism
from hypokrates.drugbank.store import DrugBankStore
from hypokrates.exceptions import ConfigurationError

GOLDEN_XML = Path(__file__).parent.parent / "golden_data" / "drugbank" / "sample_drugbank.xml"


@pytest.fixture()
def loaded_store(tmp_path: Path) -> DrugBankStore:
    """DrugBankStore carregado com golden data."""
    db_path = tmp_path / "test_drugbank.duckdb"
    store = DrugBankStore(db_path)
    store.load_from_xml(str(GOLDEN_XML))
    return store


class TestDrugInfo:
    """Testes para drug_info()."""

    async def test_found(self, loaded_store: DrugBankStore) -> None:
        info = await drug_info("propofol", _store=loaded_store)
        assert info is not None
        assert info.drugbank_id == "DB00818"
        assert info.name == "Propofol"

    async def test_not_found(self, loaded_store: DrugBankStore) -> None:
        info = await drug_info("nonexistent", _store=loaded_store)
        assert info is None

    async def test_by_synonym(self, loaded_store: DrugBankStore) -> None:
        info = await drug_info("Diprivan", _store=loaded_store)
        assert info is not None
        assert info.name == "Propofol"

    async def test_includes_targets(self, loaded_store: DrugBankStore) -> None:
        info = await drug_info("propofol", _store=loaded_store)
        assert info is not None
        assert len(info.targets) == 1
        assert info.targets[0].gene_name == "GABRA1"

    async def test_includes_enzymes(self, loaded_store: DrugBankStore) -> None:
        info = await drug_info("propofol", _store=loaded_store)
        assert info is not None
        assert len(info.enzymes) == 2
        gene_names = [e.gene_name for e in info.enzymes]
        assert "CYP2B6" in gene_names

    async def test_without_store_and_no_config_raises(self) -> None:
        DrugBankStore.reset()
        with pytest.raises(ConfigurationError, match="DrugBank XML path not configured"):
            await drug_info("propofol")


class TestDrugInteractions:
    """Testes para drug_interactions()."""

    async def test_found(self, loaded_store: DrugBankStore) -> None:
        interactions = await drug_interactions("propofol", _store=loaded_store)
        assert len(interactions) == 2
        partner_names = [i.partner_name for i in interactions]
        assert "Fentanyl" in partner_names

    async def test_not_found(self, loaded_store: DrugBankStore) -> None:
        interactions = await drug_interactions("nonexistent", _store=loaded_store)
        assert interactions == []

    async def test_sugammadex_has_interactions(self, loaded_store: DrugBankStore) -> None:
        interactions = await drug_interactions("sugammadex", _store=loaded_store)
        assert len(interactions) == 1
        assert interactions[0].partner_name == "Rocuronium"


class TestDrugMechanism:
    """Testes para drug_mechanism()."""

    async def test_found(self, loaded_store: DrugBankStore) -> None:
        moa = await drug_mechanism("propofol", _store=loaded_store)
        assert "GABA-A" in moa

    async def test_not_found(self, loaded_store: DrugBankStore) -> None:
        moa = await drug_mechanism("nonexistent", _store=loaded_store)
        assert moa == ""

    async def test_sugammadex(self, loaded_store: DrugBankStore) -> None:
        moa = await drug_mechanism("sugammadex", _store=loaded_store)
        assert "rocuronium" in moa.lower() or "encapsulates" in moa.lower()
