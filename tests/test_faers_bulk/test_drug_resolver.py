"""Testes para faers_bulk/drug_resolver.py — resolução de nomes de droga."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import pytest

from hypokrates.faers_bulk.drug_resolver import clear_cache, resolve_bulk_drug
from hypokrates.faers_bulk.store import FAERSBulkStore
from hypokrates.models import MetaInfo

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


class TestResolveBulkDrugRxNorm:
    """Resolução via RxNorm (tier 2) quando nome exato não encontrado."""

    async def test_rxnorm_resolves_brand_to_generic(self, loaded_store: FAERSBulkStore) -> None:
        """Nome que não bate direto mas RxNorm resolve para generic → encontra."""
        from unittest.mock import AsyncMock, patch

        from hypokrates.vocab.models import DrugNormResult

        clear_cache()

        mock_norm_result = DrugNormResult(
            original="diprivan",
            generic_name="propofol",
            rxcui="8782",
            meta=MetaInfo(source="test", retrieved_at=datetime.now(UTC)),
        )

        with patch(
            "hypokrates.vocab.api.normalize_drug", new_callable=AsyncMock
        ) as mock_normalize:
            mock_normalize.return_value = mock_norm_result
            result = await resolve_bulk_drug("diprivan", store=loaded_store)

        # Resolveu via RxNorm para PROPOFOL (que existe no golden store)
        assert result == "PROPOFOL"

    async def test_rxnorm_failure_returns_none(self, loaded_store: FAERSBulkStore) -> None:
        """RxNorm falha → retorna None (não crash)."""
        from unittest.mock import AsyncMock, patch

        clear_cache()

        with patch(
            "hypokrates.vocab.api.normalize_drug", new_callable=AsyncMock
        ) as mock_normalize:
            mock_normalize.side_effect = RuntimeError("RxNorm down")
            result = await resolve_bulk_drug("COMPLETAMENTE_DESCONHECIDO", store=loaded_store)

        assert result is None

    async def test_rxnorm_resolves_but_generic_not_in_store(
        self, loaded_store: FAERSBulkStore
    ) -> None:
        """RxNorm resolve para generic, mas generic não existe no store → None."""
        from unittest.mock import AsyncMock, patch

        from hypokrates.vocab.models import DrugNormResult

        clear_cache()

        mock_norm_result = DrugNormResult(
            original="rare_brand",
            generic_name="veryraredrug",
            rxcui="99999",
            meta=MetaInfo(source="test", retrieved_at=datetime.now(UTC)),
        )

        with patch(
            "hypokrates.vocab.api.normalize_drug", new_callable=AsyncMock
        ) as mock_normalize:
            mock_normalize.return_value = mock_norm_result
            result = await resolve_bulk_drug("rare_brand", store=loaded_store)

        assert result is None

    async def test_rxnorm_same_as_input(self, loaded_store: FAERSBulkStore) -> None:
        """RxNorm retorna mesmo nome que input → não re-query (já foi testado em tier 1)."""
        from unittest.mock import AsyncMock, patch

        from hypokrates.vocab.models import DrugNormResult

        clear_cache()

        mock_norm_result = DrugNormResult(
            original="DOESNOTEXIST",
            generic_name="DOESNOTEXIST",
            rxcui="0",
            meta=MetaInfo(source="test", retrieved_at=datetime.now(UTC)),
        )

        with patch(
            "hypokrates.vocab.api.normalize_drug", new_callable=AsyncMock
        ) as mock_normalize:
            mock_normalize.return_value = mock_norm_result
            result = await resolve_bulk_drug("DOESNOTEXIST", store=loaded_store)

        # Same name, skip tier 2 re-check → None
        assert result is None
