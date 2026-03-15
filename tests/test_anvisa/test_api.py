"""Testes da API ANVISA."""

from __future__ import annotations

from pathlib import Path

import pytest

from hypokrates.anvisa.api import (
    buscar_medicamento,
    buscar_por_substancia,
    listar_apresentacoes,
    mapear_nome,
)
from hypokrates.anvisa.store import AnvisaStore

GOLDEN_CSV = Path(__file__).parent.parent / "golden_data" / "anvisa" / "sample_medicamentos.csv"


@pytest.fixture()
def store(tmp_path: Path) -> AnvisaStore:
    """Cria store com golden data."""
    db_path = tmp_path / "anvisa_api_test.duckdb"
    s = AnvisaStore(db_path=db_path)
    s.load_from_csv(GOLDEN_CSV)
    return s


class TestBuscarMedicamento:
    async def test_basic_search(self, store: AnvisaStore) -> None:
        result = await buscar_medicamento("PROPOFOL", _store=store)
        assert result.total >= 1

    async def test_partial_search(self, store: AnvisaStore) -> None:
        result = await buscar_medicamento("METF", _store=store)
        assert result.total >= 1

    async def test_case_insensitive(self, store: AnvisaStore) -> None:
        result = await buscar_medicamento("novalgina", _store=store)
        assert result.total >= 1

    async def test_not_found(self, store: AnvisaStore) -> None:
        result = await buscar_medicamento("XYZXYZ", _store=store)
        assert result.total == 0


class TestBuscarPorSubstancia:
    async def test_metformina(self, store: AnvisaStore) -> None:
        result = await buscar_por_substancia("METFORMINA", _store=store)
        assert result.total >= 1

    async def test_with_category(self, store: AnvisaStore) -> None:
        result = await buscar_por_substancia("METFORMINA", categoria="rico", _store=store)
        assert result.total >= 1

    async def test_propofol(self, store: AnvisaStore) -> None:
        result = await buscar_por_substancia("PROPOFOL", _store=store)
        assert result.total >= 1


class TestMapearNome:
    async def test_dipirona(self, store: AnvisaStore) -> None:
        mapping = await mapear_nome("DIPIRONA", _store=store)
        assert mapping is not None
        assert mapping.nome_en == "METAMIZOLE"
        assert mapping.source == "static"

    async def test_reverse(self, store: AnvisaStore) -> None:
        mapping = await mapear_nome("ACETAMINOPHEN", _store=store)
        assert mapping is not None
        assert "PARACETAMOL" in mapping.nome_pt

    async def test_not_found(self, store: AnvisaStore) -> None:
        mapping = await mapear_nome("XYZXYZ_NAOEXISTE", _store=store)
        assert mapping is None


class TestListarApresentacoes:
    async def test_basic(self, store: AnvisaStore) -> None:
        result = await listar_apresentacoes("PROPOFOL", _store=store)
        assert result.total >= 1
