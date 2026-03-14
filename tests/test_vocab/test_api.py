"""Testes para hypokrates.vocab.api."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

from hypokrates.vocab.api import map_to_mesh, normalize_drug
from tests.helpers import load_golden


@patch("hypokrates.vocab.api.RxNormClient")
async def test_normalize_drug_found(mock_client_cls: AsyncMock) -> None:
    """'advil' → generic_name='ibuprofen'."""
    golden = load_golden("vocab", "rxnorm_drugs_ibuprofen.json")
    instance = AsyncMock()
    instance.search.return_value = golden
    mock_client_cls.return_value = instance

    result = await normalize_drug("advil")

    assert result.original == "advil"
    assert result.generic_name == "ibuprofen"
    assert "Advil" in result.brand_names
    assert result.rxcui == "5640"
    assert result.meta.source == "RxNorm"
    instance.close.assert_called_once()


@patch("hypokrates.vocab.api.RxNormClient")
async def test_normalize_drug_not_found(mock_client_cls: AsyncMock) -> None:
    """'xyz123' → generic_name=None."""
    golden = load_golden("vocab", "rxnorm_drugs_not_found.json")
    instance = AsyncMock()
    instance.search.return_value = golden
    mock_client_cls.return_value = instance

    result = await normalize_drug("xyz123")

    assert result.original == "xyz123"
    assert result.generic_name is None
    assert result.brand_names == []
    assert result.rxcui is None


@patch("hypokrates.vocab.api.MeSHClient")
async def test_map_to_mesh_found(mock_client_cls: AsyncMock) -> None:
    """'aspirin' → mesh_term='Aspirin', mesh_id='D001241'."""
    search_golden = load_golden("vocab", "mesh_search_aspirin.json")
    summary_golden = load_golden("vocab", "mesh_summary_aspirin.json")
    instance = AsyncMock()
    instance.search.return_value = search_golden
    instance.fetch_descriptor.return_value = summary_golden
    mock_client_cls.return_value = instance

    result = await map_to_mesh("aspirin")

    assert result.query == "aspirin"
    assert result.mesh_id == "D001241"
    assert result.mesh_term == "Aspirin"
    assert result.meta.source == "NCBI/MeSH"
    instance.close.assert_called_once()


@patch("hypokrates.vocab.api.MeSHClient")
async def test_map_to_mesh_not_found(mock_client_cls: AsyncMock) -> None:
    """'xyz123' → mesh_term=None."""
    instance = AsyncMock()
    instance.search.return_value = {"esearchresult": {"idlist": []}}
    mock_client_cls.return_value = instance

    result = await map_to_mesh("xyz123")

    assert result.query == "xyz123"
    assert result.mesh_term is None
    assert result.mesh_id is None
    assert result.tree_numbers == []
    instance.fetch_descriptor.assert_not_called()


@patch("hypokrates.vocab.api.MeSHClient")
async def test_map_to_mesh_with_tree_numbers(mock_client_cls: AsyncMock) -> None:
    """Verifica tree_numbers populados."""
    search_golden = load_golden("vocab", "mesh_search_aspirin.json")
    summary_golden = load_golden("vocab", "mesh_summary_aspirin.json")
    instance = AsyncMock()
    instance.search.return_value = search_golden
    instance.fetch_descriptor.return_value = summary_golden
    mock_client_cls.return_value = instance

    result = await map_to_mesh("aspirin")

    assert len(result.tree_numbers) == 2
    assert "D02.455.426.559.389.657.109" in result.tree_numbers
    assert "D09.698.629.200" in result.tree_numbers
