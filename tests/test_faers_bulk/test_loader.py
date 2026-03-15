"""Testes para faers_bulk/loader.py — orquestrador de carga."""

from __future__ import annotations

import shutil
from pathlib import Path

import pytest

from hypokrates.faers_bulk.loader import load_all_quarters, load_incremental
from hypokrates.faers_bulk.store import FAERSBulkStore

GOLDEN_DIR = Path(__file__).parent.parent / "golden_data" / "faers_bulk"


@pytest.fixture()
def store(tmp_path: Path) -> FAERSBulkStore:
    """FAERSBulkStore vazio em diretório temporário — singleton."""
    db_path = tmp_path / "test_loader.duckdb"
    store = FAERSBulkStore(db_path)
    FAERSBulkStore._instance = store
    yield store  # type: ignore[misc]
    FAERSBulkStore._instance = None


@pytest.fixture()
def zip_dir(tmp_path: Path) -> Path:
    """Diretório temporário com cópia dos golden ZIPs."""
    dest = tmp_path / "zips"
    dest.mkdir()
    for f in GOLDEN_DIR.glob("faers_ascii_*.zip"):
        shutil.copy2(f, dest / f.name)
    return dest


class TestLoadAllQuarters:
    """Testes de load_all_quarters."""

    async def test_loads_all(self, store: FAERSBulkStore, zip_dir: Path) -> None:
        """Carrega todos os ZIPs do diretório."""
        total = await load_all_quarters(zip_dir)
        assert total > 0
        assert store.is_loaded()

    async def test_empty_dir(self, store: FAERSBulkStore, tmp_path: Path) -> None:
        """Diretório vazio retorna 0."""
        empty = tmp_path / "empty"
        empty.mkdir()
        total = await load_all_quarters(empty)
        assert total == 0

    async def test_progress_callback(self, store: FAERSBulkStore, zip_dir: Path) -> None:
        """Callback de progresso é chamado."""
        progress_calls: list[tuple[int, int, str]] = []

        def on_progress(completed: int, total: int, key: str) -> None:
            progress_calls.append((completed, total, key))

        await load_all_quarters(zip_dir, on_progress=on_progress)
        assert len(progress_calls) == 2  # 2 ZIPs no golden data


class TestLoadIncremental:
    """Testes de load_incremental."""

    async def test_incremental_skips_loaded(self, store: FAERSBulkStore, zip_dir: Path) -> None:
        """Quarters já carregados são pulados."""
        total1 = await load_all_quarters(zip_dir)
        assert total1 > 0

        # Second call should load 0
        total2 = await load_incremental(zip_dir)
        assert total2 == 0
