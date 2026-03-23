"""Testes para hypokrates.vocab.models."""

from __future__ import annotations

from hypokrates.vocab.models import DrugNormResult, MeSHResult
from tests.helpers import make_meta


class TestDrugNormResult:
    """Testes para DrugNormResult."""

    def test_construction(self) -> None:
        result = DrugNormResult(
            original="advil",
            generic_name="ibuprofen",
            brand_names=["Advil", "Motrin"],
            rxcui="5640",
            meta=make_meta(),
        )
        assert result.original == "advil"
        assert result.generic_name == "ibuprofen"
        assert result.brand_names == ["Advil", "Motrin"]
        assert result.rxcui == "5640"

    def test_roundtrip(self) -> None:
        result = DrugNormResult(
            original="advil",
            generic_name="ibuprofen",
            brand_names=["Advil"],
            rxcui="5640",
            meta=make_meta(),
        )
        data = result.model_dump()
        restored = DrugNormResult.model_validate(data)
        assert restored.original == result.original
        assert restored.generic_name == result.generic_name

    def test_generic_name_none(self) -> None:
        result = DrugNormResult(
            original="xyz123",
            meta=make_meta(),
        )
        assert result.generic_name is None
        assert result.brand_names == []
        assert result.rxcui is None


class TestMeSHResult:
    """Testes para MeSHResult."""

    def test_construction(self) -> None:
        result = MeSHResult(
            query="aspirin",
            mesh_id="D001241",
            mesh_term="Aspirin",
            tree_numbers=["D02.455.426.559.389.657.109"],
            meta=make_meta(),
        )
        assert result.query == "aspirin"
        assert result.mesh_id == "D001241"
        assert result.mesh_term == "Aspirin"
        assert len(result.tree_numbers) == 1

    def test_roundtrip(self) -> None:
        result = MeSHResult(
            query="aspirin",
            mesh_id="D001241",
            mesh_term="Aspirin",
            tree_numbers=["D02.455"],
            meta=make_meta(),
        )
        data = result.model_dump()
        restored = MeSHResult.model_validate(data)
        assert restored.query == result.query
        assert restored.mesh_id == result.mesh_id

    def test_mesh_term_none(self) -> None:
        result = MeSHResult(
            query="xyz123",
            meta=make_meta(),
        )
        assert result.mesh_term is None
        assert result.mesh_id is None
        assert result.tree_numbers == []
