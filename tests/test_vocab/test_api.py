"""Testes para hypokrates.vocab.api."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

from hypokrates.vocab.api import map_to_mesh, normalize_drug
from tests.helpers import load_golden


def _mock_client(mock_cls: AsyncMock, instance: AsyncMock) -> None:
    """Configura mock para suportar async with (context manager)."""
    instance.__aenter__.return_value = instance
    mock_cls.return_value = instance


@patch("hypokrates.vocab.api.RxNormClient")
async def test_normalize_drug_found(mock_client_cls: AsyncMock) -> None:
    """'advil' → generic_name='ibuprofen'."""
    golden = load_golden("vocab", "rxnorm_drugs_ibuprofen.json")
    instance = AsyncMock()
    instance.search.return_value = golden
    _mock_client(mock_client_cls, instance)

    result = await normalize_drug("advil")

    assert result.original == "advil"
    assert result.generic_name == "ibuprofen"
    assert "Advil" in result.brand_names
    assert result.rxcui == "5640"
    assert result.meta.source == "RxNorm"


@patch("hypokrates.vocab.api.RxNormClient")
async def test_normalize_drug_not_found(mock_client_cls: AsyncMock) -> None:
    """'xyz123' → generic_name=None."""
    golden = load_golden("vocab", "rxnorm_drugs_not_found.json")
    instance = AsyncMock()
    instance.search.return_value = golden
    instance.search_by_name.return_value = {"idGroup": {}}
    _mock_client(mock_client_cls, instance)

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
    _mock_client(mock_client_cls, instance)

    result = await map_to_mesh("aspirin")

    assert result.query == "aspirin"
    assert result.mesh_id == "D001241"
    assert result.mesh_term == "Aspirin"
    assert result.meta.source == "NCBI/MeSH"


@patch("hypokrates.vocab.api.MeSHClient")
async def test_map_to_mesh_not_found(mock_client_cls: AsyncMock) -> None:
    """'xyz123' → mesh_term=None."""
    instance = AsyncMock()
    instance.search.return_value = {"esearchresult": {"idlist": []}}
    _mock_client(mock_client_cls, instance)

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
    _mock_client(mock_client_cls, instance)

    result = await map_to_mesh("aspirin")

    assert len(result.tree_numbers) == 2
    assert "D02.455.426.559.389.657.109" in result.tree_numbers
    assert "D09.698.629.200" in result.tree_numbers


@patch("hypokrates.vocab.api.RxNormClient")
async def test_normalize_drug_rxcui_fallback(mock_client_cls: AsyncMock) -> None:
    """'Diprivan' → generic_name='propofol' via rxcui/allrelated fallback."""
    golden_drugs = load_golden("vocab", "rxnorm_drugs_not_found.json")
    golden_rxcui = load_golden("vocab", "rxnorm_rxcui_diprivan.json")
    golden_allrelated = load_golden("vocab", "rxnorm_allrelated_203220.json")

    instance = AsyncMock()
    instance.search.return_value = golden_drugs
    instance.search_by_name.return_value = golden_rxcui
    instance.fetch_allrelated.return_value = golden_allrelated
    _mock_client(mock_client_cls, instance)

    result = await normalize_drug("Diprivan")

    assert result.original == "Diprivan"
    assert result.generic_name == "propofol"
    assert result.rxcui == "8782"


@patch("hypokrates.vocab.api.RxNormClient")
async def test_normalize_drug_pt_en_fallback(mock_client_cls: AsyncMock) -> None:
    """'dipirona' → generic_name via NOME_PT_EN (metamizole)."""
    golden_not_found = load_golden("vocab", "rxnorm_drugs_not_found.json")
    # Step 1 and Step 2 fail, Step 3 tries NOME_PT_EN
    instance = AsyncMock()
    instance.search.side_effect = [golden_not_found, golden_not_found]
    instance.search_by_name.return_value = {"idGroup": {}}
    _mock_client(mock_client_cls, instance)

    result = await normalize_drug("dipirona")

    assert result.original == "dipirona"
    # Should resolve via NOME_PT_EN: DIPIRONA -> METAMIZOLE
    assert result.generic_name is not None
    assert "metamizole" in result.generic_name.lower()


@patch("hypokrates.vocab.api.MeSHClient")
async def test_map_to_mesh_ranks_by_similarity(mock_client_cls: AsyncMock) -> None:
    """MeSH ranking: 'lactic acidosis' deve preferir 'Acidosis, Lactic' sobre 'MELAS Syndrome'."""
    instance = AsyncMock()

    # Search retorna 3 UIDs
    uids = ["68000005", "68065001", "68000040"]
    instance.search.return_value = {"esearchresult": {"idlist": uids}}

    # Descriptors com termos diferentes
    instance.fetch_descriptor.side_effect = [
        {
            "result": {
                "uids": ["68000005"],
                "68000005": {
                    "ds_meshui": "D000005",
                    "ds_meshterms": ["MELAS Syndrome"],
                    "ds_treenumberlist": ["C10.228"],
                },
            }
        },
        {
            "result": {
                "uids": ["68065001"],
                "68065001": {
                    "ds_meshui": "D065001",
                    "ds_meshterms": ["Acidosis, Lactic"],
                    "ds_treenumberlist": ["C18.452.076.127"],
                },
            }
        },
        {
            "result": {
                "uids": ["68000040"],
                "68000040": {
                    "ds_meshui": "D000040",
                    "ds_meshterms": ["Acidosis"],
                    "ds_treenumberlist": ["C18.452.076"],
                },
            }
        },
    ]
    _mock_client(mock_client_cls, instance)

    result = await map_to_mesh("lactic acidosis")

    assert result.mesh_term == "Acidosis, Lactic"
    assert result.mesh_id == "D065001"


@patch("hypokrates.vocab.api.MeSHClient")
async def test_map_to_mesh_arrhythmia_not_agents(mock_client_cls: AsyncMock) -> None:
    """MeSH ranking: 'arrhythmia' → 'Arrhythmias, Cardiac' (not Agents)."""
    instance = AsyncMock()

    instance.search.return_value = {"esearchresult": {"idlist": ["68000889", "68001145"]}}

    instance.fetch_descriptor.side_effect = [
        {
            "result": {
                "uids": ["68000889"],
                "68000889": {
                    "ds_meshui": "D000889",
                    "ds_meshterms": ["Anti-Arrhythmia Agents"],
                    "ds_treenumberlist": ["D27.505.954.411.121"],
                },
            }
        },
        {
            "result": {
                "uids": ["68001145"],
                "68001145": {
                    "ds_meshui": "D001145",
                    "ds_meshterms": ["Arrhythmias, Cardiac"],
                    "ds_treenumberlist": ["C14.280.067"],
                },
            }
        },
    ]
    _mock_client(mock_client_cls, instance)

    result = await map_to_mesh("arrhythmia")

    assert result.mesh_term == "Arrhythmias, Cardiac"
    assert result.mesh_id == "D001145"


@patch("hypokrates.vocab.api.RxNormClient")
async def test_normalize_drug_paracetamol_pt_en(mock_client_cls: AsyncMock) -> None:
    """'paracetamol' → generic_name via NOME_PT_EN (acetaminophen)."""
    golden_not_found = load_golden("vocab", "rxnorm_drugs_not_found.json")
    instance = AsyncMock()
    instance.search.side_effect = [golden_not_found, golden_not_found]
    instance.search_by_name.return_value = {"idGroup": {}}
    _mock_client(mock_client_cls, instance)

    result = await normalize_drug("paracetamol")

    assert result.original == "paracetamol"
    assert result.generic_name is not None
    assert "acetaminophen" in result.generic_name.lower()
