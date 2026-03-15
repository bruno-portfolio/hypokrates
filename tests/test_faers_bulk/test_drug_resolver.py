"""Testes para faers_bulk/drug_resolver.py — resolução de nomes de droga."""

from __future__ import annotations

from pathlib import Path

import pytest

from hypokrates.faers_bulk.drug_resolver import clear_cache, resolve_bulk_drug
from hypokrates.faers_bulk.store import FAERSBulkStore

GOLDEN_ZIP_Q3 = (
    Path(__file__).parent.parent / "golden_data" / "faers_bulk" / "faers_ascii_2024Q3.zip"
)


@pytest.fixture()
def loaded_store(tmp_path: Path) -> FAERSBulkStore:
    """FAERSBulkStore com Q3 carregado."""
    db_path = tmp_path / "test_resolver.duckdb"
    store = FAERSBulkStore(db_path)
    store.load_quarter(GOLDEN_ZIP_Q3)
    clear_cache()
    return store


class TestResolveBulkDrug:
    """Testes de resolução de nomes de droga no bulk store."""

    async def test_exact_match(self, loaded_store: FAERSBulkStore) -> None:
        """Nome exato resolve diretamente."""
        result = await resolve_bulk_drug("propofol", store=loaded_store)
        assert result == "PROPOFOL"

    async def test_case_insensitive(self, loaded_store: FAERSBulkStore) -> None:
        """Busca é case-insensitive."""
        result = await resolve_bulk_drug("Propofol", store=loaded_store)
        assert result == "PROPOFOL"

    async def test_not_found(self, loaded_store: FAERSBulkStore) -> None:
        """Droga não existente retorna None."""
        result = await resolve_bulk_drug("NONEXISTENT_DRUG_XYZ", store=loaded_store)
        assert result is None

    async def test_empty_input(self, loaded_store: FAERSBulkStore) -> None:
        """Input vazio retorna None."""
        result = await resolve_bulk_drug("", store=loaded_store)
        assert result is None

    async def test_cache_hit(self, loaded_store: FAERSBulkStore) -> None:
        """Segunda chamada usa cache."""
        result1 = await resolve_bulk_drug("ketamine", store=loaded_store)
        result2 = await resolve_bulk_drug("ketamine", store=loaded_store)
        assert result1 == result2 == "KETAMINE"

    async def test_clear_cache(self, loaded_store: FAERSBulkStore) -> None:
        """clear_cache limpa o cache de resolução."""
        await resolve_bulk_drug("propofol", store=loaded_store)
        clear_cache()
        # Deve funcionar normalmente após clear
        result = await resolve_bulk_drug("propofol", store=loaded_store)
        assert result == "PROPOFOL"
