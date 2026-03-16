"""Testes para chembl/api.py — API pública."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import AsyncMock, patch

from hypokrates.chembl.api import drug_mechanism, drug_metabolism, drug_targets

GOLDEN = Path(__file__).parent.parent / "golden_data" / "chembl"


def _load(name: str) -> dict[str, object]:
    return json.loads((GOLDEN / name).read_text())  # type: ignore[return-value]


def _mock_client(mock_cls: AsyncMock, instance: AsyncMock) -> None:
    """Configura mock para suportar async with (context manager)."""
    instance.__aenter__ = AsyncMock(return_value=instance)
    mock_cls.return_value = instance


class TestDrugMechanism:
    """Testes para drug_mechanism()."""

    async def test_found(self) -> None:
        search_data = _load("search_propofol.json")
        mech_data = _load("mechanism_propofol.json")
        target_data = _load("target_gaba.json")

        with patch("hypokrates.chembl.api.ChEMBLClient") as mock_cls:
            instance = AsyncMock()
            instance.get.side_effect = [search_data, mech_data, target_data]
            _mock_client(mock_cls, instance)

            result = await drug_mechanism("propofol", use_cache=False)

        assert result.chembl_id == "CHEMBL526"
        assert "GABA-A" in result.mechanism_of_action
        assert result.action_type == "POSITIVE ALLOSTERIC MODULATOR"
        assert len(result.targets) == 1
        assert "GABRA1" in result.targets[0].gene_names

    async def test_not_found(self) -> None:
        with patch("hypokrates.chembl.api.ChEMBLClient") as mock_cls:
            instance = AsyncMock()
            instance.get.return_value = {"molecules": []}
            _mock_client(mock_cls, instance)

            result = await drug_mechanism("nonexistent", use_cache=False)

        assert result.chembl_id == ""
        assert result.mechanism_of_action == ""

    async def test_no_mechanisms(self) -> None:
        search_data = _load("search_propofol.json")

        with patch("hypokrates.chembl.api.ChEMBLClient") as mock_cls:
            instance = AsyncMock()
            instance.get.side_effect = [search_data, {"mechanisms": []}]
            _mock_client(mock_cls, instance)

            result = await drug_mechanism("propofol", use_cache=False)

        assert result.chembl_id == "CHEMBL526"
        assert result.mechanism_of_action == ""

    async def test_with_chembl_id(self) -> None:
        mech_data = _load("mechanism_propofol.json")
        target_data = _load("target_gaba.json")

        with patch("hypokrates.chembl.api.ChEMBLClient") as mock_cls:
            instance = AsyncMock()
            instance.get.side_effect = [mech_data, target_data]
            _mock_client(mock_cls, instance)

            result = await drug_mechanism("propofol", use_cache=False, _chembl_id="CHEMBL526")

        assert result.chembl_id == "CHEMBL526"
        # Não deve ter chamado search (só mechanism + target)
        assert instance.get.call_count == 2


class TestDrugTargets:
    """Testes para drug_targets()."""

    async def test_returns_gene_names(self) -> None:
        search_data = _load("search_propofol.json")
        mech_data = _load("mechanism_propofol.json")
        target_data = _load("target_gaba.json")

        with patch("hypokrates.chembl.api.ChEMBLClient") as mock_cls:
            instance = AsyncMock()
            instance.get.side_effect = [search_data, mech_data, target_data]
            _mock_client(mock_cls, instance)

            genes = await drug_targets("propofol", use_cache=False)

        assert "GABRA1" in genes
        assert "GABRB2" in genes

    async def test_not_found_returns_empty(self) -> None:
        with patch("hypokrates.chembl.api.ChEMBLClient") as mock_cls:
            instance = AsyncMock()
            instance.get.return_value = {"molecules": []}
            _mock_client(mock_cls, instance)

            genes = await drug_targets("nonexistent", use_cache=False)

        assert genes == []


class TestDrugMetabolism:
    """Testes para drug_metabolism()."""

    async def test_found(self) -> None:
        search_data = _load("search_propofol.json")
        met_data = _load("metabolism_propofol.json")

        with patch("hypokrates.chembl.api.ChEMBLClient") as mock_cls:
            instance = AsyncMock()
            instance.get.side_effect = [search_data, met_data]
            _mock_client(mock_cls, instance)

            result = await drug_metabolism("propofol", use_cache=False)

        assert result.chembl_id == "CHEMBL526"
        assert len(result.pathways) == 2
        assert result.pathways[0].conversion == "Glucuronidation"

    async def test_not_found(self) -> None:
        with patch("hypokrates.chembl.api.ChEMBLClient") as mock_cls:
            instance = AsyncMock()
            instance.get.return_value = {"molecules": []}
            _mock_client(mock_cls, instance)

            result = await drug_metabolism("nonexistent", use_cache=False)

        assert result.chembl_id == ""
        assert result.pathways == []
