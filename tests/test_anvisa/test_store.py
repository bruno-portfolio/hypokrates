"""Testes do store ANVISA."""

from __future__ import annotations

from pathlib import Path

import pytest

from hypokrates.anvisa.store import AnvisaStore

GOLDEN_CSV = Path(__file__).parent.parent / "golden_data" / "anvisa" / "sample_medicamentos.csv"


@pytest.fixture()
def store(tmp_path: Path) -> AnvisaStore:
    """Cria store com golden data em tmp_path."""
    db_path = tmp_path / "anvisa_test.duckdb"
    s = AnvisaStore(db_path=db_path)
    s.load_from_csv(GOLDEN_CSV)
    return s


@pytest.fixture()
def empty_store(tmp_path: Path) -> AnvisaStore:
    """Cria store vazio."""
    db_path = tmp_path / "anvisa_empty.duckdb"
    return AnvisaStore(db_path=db_path)


class TestStoreLoad:
    def test_empty_not_loaded(self, empty_store: AnvisaStore) -> None:
        assert not empty_store.loaded

    def test_load_golden(self, store: AnvisaStore) -> None:
        assert store.loaded

    def test_loaded_at(self, store: AnvisaStore) -> None:
        loaded_at = store.get_loaded_at()
        assert loaded_at is not None

    def test_reload_idempotent(self, store: AnvisaStore, tmp_path: Path) -> None:
        """Recarregar nao deve falhar (DELETE + INSERT)."""
        count = store.load_from_csv(GOLDEN_CSV)
        assert count == 9


class TestSearch:
    def test_by_name_exact(self, store: AnvisaStore) -> None:
        result = store.search("NOVALGINA")
        assert result.total >= 1
        names = [m.nome_produto.upper() for m in result.medicamentos]
        assert any("NOVALGINA" in n for n in names)

    def test_by_name_partial(self, store: AnvisaStore) -> None:
        result = store.search("METF")
        assert result.total >= 1

    def test_case_insensitive(self, store: AnvisaStore) -> None:
        result = store.search("novalgina")
        assert result.total >= 1

    def test_by_substancia_propofol(self, store: AnvisaStore) -> None:
        result = store.search("PROPOFOL")
        assert result.total >= 1

    def test_english_name_mapping(self, store: AnvisaStore) -> None:
        """Buscar 'KETAMINE' deve encontrar 'CETAMINA' via mapeamento EN->PT."""
        result = store.search("KETAMINE")
        assert result.total >= 1

    def test_not_found(self, store: AnvisaStore) -> None:
        result = store.search("XYZDROGA_INEXISTENTE")
        assert result.total == 0

    def test_limit(self, store: AnvisaStore) -> None:
        result = store.search("DIPIRONA", limit=1)
        assert len(result.medicamentos) <= 1

    def test_empty_query(self, store: AnvisaStore) -> None:
        result = store.search("")
        assert result.total == 0


class TestSearchBySubstancia:
    def test_metformina(self, store: AnvisaStore) -> None:
        result = store.search_by_substancia("METFORMINA")
        assert result.total >= 1

    def test_filter_generico(self, store: AnvisaStore) -> None:
        result = store.search_by_substancia("METFORMINA", categoria="rico")
        assert result.total >= 1

    def test_english_name(self, store: AnvisaStore) -> None:
        result = store.search_by_substancia("METFORMIN")
        assert result.total >= 1

    def test_propofol(self, store: AnvisaStore) -> None:
        result = store.search_by_substancia("PROPOFOL")
        assert result.total >= 1


class TestMapNome:
    def test_pt_to_en(self, store: AnvisaStore) -> None:
        mapping = store.map_nome("DIPIRONA")
        assert mapping is not None
        assert mapping.nome_en == "METAMIZOLE"

    def test_en_to_pt(self, store: AnvisaStore) -> None:
        mapping = store.map_nome("METAMIZOLE")
        assert mapping is not None
        assert "DIPIRONA" in mapping.nome_pt

    def test_not_found(self, store: AnvisaStore) -> None:
        mapping = store.map_nome("DROGA_INEXISTENTE_XYZ")
        assert mapping is None

    def test_cetamina(self, store: AnvisaStore) -> None:
        mapping = store.map_nome("CETAMINA")
        assert mapping is not None
        assert mapping.nome_en == "KETAMINE"

    def test_empty(self, store: AnvisaStore) -> None:
        mapping = store.map_nome("")
        assert mapping is None


class TestSingleton:
    def test_get_instance(self, tmp_path: Path) -> None:
        """Singleton retorna mesma instancia."""
        # Resetar singleton antes
        AnvisaStore.reset()
        try:
            # Criar com path customizado via config
            from hypokrates.config import configure, reset_config

            configure(cache_dir=tmp_path)
            s1 = AnvisaStore.get_instance()
            s2 = AnvisaStore.get_instance()
            assert s1 is s2
        finally:
            AnvisaStore.reset()
            reset_config()

    def test_reset(self, tmp_path: Path) -> None:
        """Reset limpa singleton."""
        AnvisaStore.reset()
        try:
            from hypokrates.config import configure, reset_config

            configure(cache_dir=tmp_path)
            s1 = AnvisaStore.get_instance()
            assert s1 is not None
            AnvisaStore.reset()
            s2 = AnvisaStore.get_instance()
            assert s2 is not s1
        finally:
            AnvisaStore.reset()
            reset_config()

    def test_close(self, store: AnvisaStore) -> None:
        """Close nao causa erro."""
        store.close()


class TestMedicamentoModel:
    def test_propofol_has_substancias(self, store: AnvisaStore) -> None:
        result = store.search("PROPOFOL")
        assert result.total >= 1
        med = result.medicamentos[0]
        assert any("PROPOFOL" in s.upper() for s in med.substancias)

    def test_has_empresa(self, store: AnvisaStore) -> None:
        result = store.search("NOVALGINA")
        assert result.total >= 1
        med = result.medicamentos[0]
        assert med.empresa  # nao vazio

    def test_image_url_default_none(self, store: AnvisaStore) -> None:
        result = store.search("PROPOFOL")
        assert result.total >= 1
        assert result.medicamentos[0].image_url is None
