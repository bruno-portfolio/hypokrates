"""Testes para drugbank/parser.py — iterparse de XML."""

from __future__ import annotations

from pathlib import Path

import pytest

from hypokrates.drugbank.parser import iterparse_drugbank

GOLDEN_XML = Path(__file__).parent.parent / "golden_data" / "drugbank" / "sample_drugbank.xml"


class TestIterParseDrugbank:
    """Testes de parsing do XML do DrugBank."""

    def test_parses_all_drugs(self) -> None:
        drugs = iterparse_drugbank(str(GOLDEN_XML))
        assert len(drugs) == 3

    def test_propofol_basic_fields(self) -> None:
        drugs = iterparse_drugbank(str(GOLDEN_XML))
        propofol = next(d for d in drugs if d["name"] == "Propofol")
        assert propofol["drugbank_id"] == "DB00818"
        assert "GABA-A" in propofol["mechanism_of_action"]
        assert "intravenous anesthetic" in propofol["description"]

    def test_propofol_categories(self) -> None:
        drugs = iterparse_drugbank(str(GOLDEN_XML))
        propofol = next(d for d in drugs if d["name"] == "Propofol")
        assert "Anesthetics, Intravenous" in propofol["categories"]

    def test_propofol_synonyms(self) -> None:
        drugs = iterparse_drugbank(str(GOLDEN_XML))
        propofol = next(d for d in drugs if d["name"] == "Propofol")
        assert "Propofol" in propofol["synonyms"]
        assert "Diprivan" in propofol["synonyms"]

    def test_propofol_targets(self) -> None:
        drugs = iterparse_drugbank(str(GOLDEN_XML))
        propofol = next(d for d in drugs if d["name"] == "Propofol")
        assert len(propofol["targets"]) == 1
        target = propofol["targets"][0]
        assert target["gene_name"] == "GABRA1"
        assert "potentiator" in target["actions"]

    def test_propofol_enzymes(self) -> None:
        drugs = iterparse_drugbank(str(GOLDEN_XML))
        propofol = next(d for d in drugs if d["name"] == "Propofol")
        assert len(propofol["enzymes"]) == 2
        gene_names = [e["gene_name"] for e in propofol["enzymes"]]
        assert "CYP2B6" in gene_names
        assert "UGT1A9" in gene_names

    def test_propofol_interactions(self) -> None:
        drugs = iterparse_drugbank(str(GOLDEN_XML))
        propofol = next(d for d in drugs if d["name"] == "Propofol")
        assert len(propofol["interactions"]) == 2
        partner_names = [i["partner_name"] for i in propofol["interactions"]]
        assert "Fentanyl" in partner_names
        assert "Sevoflurane" in partner_names

    def test_sugammadex_no_enzymes(self) -> None:
        drugs = iterparse_drugbank(str(GOLDEN_XML))
        sug = next(d for d in drugs if d["name"] == "Sugammadex")
        assert sug["enzymes"] == []

    def test_sugammadex_target(self) -> None:
        drugs = iterparse_drugbank(str(GOLDEN_XML))
        sug = next(d for d in drugs if d["name"] == "Sugammadex")
        assert len(sug["targets"]) == 1
        assert sug["targets"][0]["name"] == "Rocuronium"

    def test_nonexistent_file_raises(self) -> None:
        with pytest.raises(FileNotFoundError):
            iterparse_drugbank("/nonexistent/path.xml")

    def test_sevoflurane_fields(self) -> None:
        drugs = iterparse_drugbank(str(GOLDEN_XML))
        sevo = next(d for d in drugs if d["name"] == "Sevoflurane")
        assert sevo["drugbank_id"] == "DB01236"
        assert len(sevo["enzymes"]) == 1
        assert sevo["enzymes"][0]["gene_name"] == "CYP2E1"

    def test_all_have_primary_id(self) -> None:
        drugs = iterparse_drugbank(str(GOLDEN_XML))
        for drug in drugs:
            assert drug["drugbank_id"].startswith("DB")
