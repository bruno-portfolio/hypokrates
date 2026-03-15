"""Testes para hypokrates.vocab.parser."""

from __future__ import annotations

from hypokrates.vocab.parser import parse_mesh_descriptor, parse_mesh_search, parse_rxnorm_drugs
from tests.helpers import load_golden


class TestParseRxNormDrugs:
    """Testes para parse_rxnorm_drugs."""

    def test_normal_response(self) -> None:
        data = load_golden("vocab", "rxnorm_drugs_ibuprofen.json")
        generic, brands, rxcui = parse_rxnorm_drugs(data)

        assert generic == "ibuprofen"
        assert "Advil" in brands
        assert "Motrin" in brands
        assert rxcui == "5640"

    def test_not_found(self) -> None:
        data = load_golden("vocab", "rxnorm_drugs_not_found.json")
        generic, brands, rxcui = parse_rxnorm_drugs(data)

        assert generic is None
        assert brands == []
        assert rxcui is None

    def test_no_concept_group(self) -> None:
        data = {"drugGroup": {"name": "test"}}
        generic, brands, rxcui = parse_rxnorm_drugs(data)

        assert generic is None
        assert brands == []
        assert rxcui is None

    def test_empty_drug_group(self) -> None:
        data = {"drugGroup": {}}
        generic, brands, rxcui = parse_rxnorm_drugs(data)

        assert generic is None
        assert brands == []
        assert rxcui is None

    def test_tty_filtering(self) -> None:
        """Apenas IN e BN são extraídos, outros ttys ignorados."""
        data = {
            "drugGroup": {
                "name": "test",
                "conceptGroup": [
                    {
                        "tty": "SCD",
                        "conceptProperties": [{"rxcui": "999", "name": "SCD Form"}],
                    },
                    {
                        "tty": "IN",
                        "conceptProperties": [{"rxcui": "100", "name": "generic_drug"}],
                    },
                ],
            }
        }
        generic, brands, rxcui = parse_rxnorm_drugs(data)

        assert generic == "generic_drug"
        assert rxcui == "100"
        assert brands == []


class TestParseMeSHSearch:
    """Testes para parse_mesh_search."""

    def test_normal_response(self) -> None:
        data = load_golden("vocab", "mesh_search_aspirin.json")
        uids = parse_mesh_search(data)

        assert uids == ["68001241"]

    def test_no_idlist(self) -> None:
        data = {"esearchresult": {}}
        uids = parse_mesh_search(data)

        assert uids == []

    def test_empty_esearchresult(self) -> None:
        data = {}
        uids = parse_mesh_search(data)

        assert uids == []


class TestParseMeSHDescriptor:
    """Testes para parse_mesh_descriptor."""

    def test_normal_response(self) -> None:
        data = load_golden("vocab", "mesh_summary_aspirin.json")
        mesh_id, mesh_term, tree_numbers = parse_mesh_descriptor(data)

        assert mesh_id == "D001241"
        assert mesh_term == "Aspirin"
        assert len(tree_numbers) == 2

    def test_no_uids(self) -> None:
        data = {"result": {"uids": []}}
        mesh_id, mesh_term, tree_numbers = parse_mesh_descriptor(data)

        assert mesh_id is None
        assert mesh_term is None
        assert tree_numbers == []

    def test_no_meshterms(self) -> None:
        data = {
            "result": {
                "uids": ["12345"],
                "12345": {
                    "uid": "12345",
                    "ds_meshui": "D999999",
                },
            }
        }
        mesh_id, mesh_term, tree_numbers = parse_mesh_descriptor(data)

        assert mesh_id == "D999999"
        assert mesh_term is None
        assert tree_numbers == []

    def test_uid_not_dict(self) -> None:
        data = {"result": {"uids": ["12345"], "12345": "invalid"}}
        mesh_id, mesh_term, _tree_numbers = parse_mesh_descriptor(data)

        assert mesh_id is None
        assert mesh_term is None


class TestParseRxCuiResponse:
    """Testes para parse_rxcui_response."""

    def test_found(self) -> None:
        from hypokrates.vocab.parser import parse_rxcui_response

        data = load_golden("vocab", "rxnorm_rxcui_diprivan.json")
        rxcui = parse_rxcui_response(data)
        assert rxcui == "203220"

    def test_not_found(self) -> None:
        from hypokrates.vocab.parser import parse_rxcui_response

        rxcui = parse_rxcui_response({"idGroup": {}})
        assert rxcui is None

    def test_empty_id_list(self) -> None:
        from hypokrates.vocab.parser import parse_rxcui_response

        rxcui = parse_rxcui_response({"idGroup": {"rxnormId": []}})
        assert rxcui is None


class TestParseAllrelatedIngredient:
    """Testes para parse_allrelated_ingredient."""

    def test_found(self) -> None:
        from hypokrates.vocab.parser import parse_allrelated_ingredient

        data = load_golden("vocab", "rxnorm_allrelated_203220.json")
        name, rxcui = parse_allrelated_ingredient(data)
        assert name == "propofol"
        assert rxcui == "8782"

    def test_no_ingredient(self) -> None:
        from hypokrates.vocab.parser import parse_allrelated_ingredient

        data = {
            "allRelatedGroup": {
                "conceptGroup": [
                    {"tty": "BN", "conceptProperties": [{"name": "Diprivan", "rxcui": "1"}]},
                ]
            }
        }
        name, rxcui = parse_allrelated_ingredient(data)
        assert name is None
        assert rxcui is None

    def test_empty_response(self) -> None:
        from hypokrates.vocab.parser import parse_allrelated_ingredient

        name, rxcui = parse_allrelated_ingredient({})
        assert name is None
        assert rxcui is None
