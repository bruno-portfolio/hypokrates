"""Testes para chembl/parser.py."""

from __future__ import annotations

import json
from pathlib import Path

from hypokrates.chembl.parser import (
    parse_mechanisms,
    parse_metabolism,
    parse_molecule_name,
    parse_molecule_search,
    parse_target,
)

GOLDEN = Path(__file__).parent.parent / "golden_data" / "chembl"


class TestParseMoleculeSearch:
    """Testes para parse_molecule_search()."""

    def test_found(self) -> None:
        data = json.loads((GOLDEN / "search_propofol.json").read_text())
        result = parse_molecule_search(data)
        assert result == "CHEMBL526"

    def test_empty_molecules(self) -> None:
        assert parse_molecule_search({"molecules": []}) is None

    def test_missing_molecules(self) -> None:
        assert parse_molecule_search({}) is None


class TestParseMoleculeName:
    """Testes para parse_molecule_name()."""

    def test_found(self) -> None:
        data = json.loads((GOLDEN / "search_propofol.json").read_text())
        assert parse_molecule_name(data) == "PROPOFOL"

    def test_empty(self) -> None:
        assert parse_molecule_name({"molecules": []}) == ""


class TestParseMechanisms:
    """Testes para parse_mechanisms()."""

    def test_parses_mechanisms(self) -> None:
        data = json.loads((GOLDEN / "mechanism_propofol.json").read_text())
        mechs = parse_mechanisms(data)
        assert len(mechs) == 1
        assert "GABA-A" in mechs[0]["mechanism_of_action"]
        assert mechs[0]["action_type"] == "POSITIVE ALLOSTERIC MODULATOR"
        assert mechs[0]["target_chembl_id"] == "CHEMBL2093872"
        assert mechs[0]["max_phase"] == 4

    def test_empty(self) -> None:
        assert parse_mechanisms({"mechanisms": []}) == []
        assert parse_mechanisms({}) == []


class TestParseTarget:
    """Testes para parse_target()."""

    def test_parses_gene_names(self) -> None:
        data = json.loads((GOLDEN / "target_gaba.json").read_text())
        target = parse_target(data)
        assert target.target_chembl_id == "CHEMBL2093872"
        assert target.name == "GABA-A receptor; anion channel"
        assert "GABRA1" in target.gene_names
        assert "GABRB2" in target.gene_names
        assert "GABRG2" in target.gene_names
        assert target.organism == "Homo sapiens"

    def test_empty_components(self) -> None:
        target = parse_target({"target_chembl_id": "X", "pref_name": "Test"})
        assert target.gene_names == []

    def test_no_gene_symbol_synonyms(self) -> None:
        data = {
            "target_chembl_id": "X",
            "pref_name": "Test",
            "target_components": [
                {
                    "target_component_synonyms": [
                        {"component_synonym": "Foo", "syn_type": "UNIPROT"}
                    ]
                }
            ],
        }
        target = parse_target(data)
        assert target.gene_names == []


class TestParseMetabolism:
    """Testes para parse_metabolism()."""

    def test_parses_pathways(self) -> None:
        data = json.loads((GOLDEN / "metabolism_propofol.json").read_text())
        pathways = parse_metabolism(data)
        assert len(pathways) == 2
        assert pathways[0].conversion == "Glucuronidation"
        assert pathways[0].substrate_name == "Propofol"
        assert pathways[0].metabolite_name == "Propofol glucuronide"
        assert pathways[1].conversion == "Oxidation"

    def test_empty(self) -> None:
        assert parse_metabolism({"metabolisms": []}) == []
        assert parse_metabolism({}) == []

    def test_null_enzyme(self) -> None:
        data = json.loads((GOLDEN / "metabolism_propofol.json").read_text())
        pathways = parse_metabolism(data)
        assert pathways[0].enzyme_name == ""
