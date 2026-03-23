"""Tests for BaseDuckDBStore — singleton isolation, lock helpers."""

from __future__ import annotations

from pathlib import Path

from hypokrates.store.base import BaseDuckDBStore

_TEST_SQL = "CREATE TABLE IF NOT EXISTS t (id INTEGER PRIMARY KEY, name VARCHAR)"


class StoreA(BaseDuckDBStore):
    _DB_FILENAME = "store_a.duckdb"
    _CREATE_TABLES = _TEST_SQL


class StoreB(BaseDuckDBStore):
    _DB_FILENAME = "store_b.duckdb"
    _CREATE_TABLES = _TEST_SQL


class TestInitSubclass:
    def test_separate_singletons(self) -> None:
        """__init_subclass__ cria _instance e _lock separados por subclasse."""
        assert StoreA._instance is None
        assert StoreB._instance is None
        assert StoreA._lock is not StoreB._lock

    def test_base_class_has_own_lock(self) -> None:
        assert BaseDuckDBStore._lock is not StoreA._lock


class TestSingleton:
    def test_get_instance_and_reset(self, tmp_path: Path) -> None:
        """get_instance cria singleton; reset limpa."""
        from hypokrates.config import configure

        configure(cache_dir=tmp_path)

        a1 = StoreA.get_instance()
        a2 = StoreA.get_instance()
        assert a1 is a2

        # StoreB independente
        b1 = StoreB.get_instance()
        assert b1 is not a1

        StoreA.reset()
        assert StoreA._instance is None
        # StoreB nao foi afetado
        assert StoreB._instance is b1

        StoreB.reset()

    def test_close(self, tmp_path: Path) -> None:
        store = StoreA(db_path=tmp_path / "test_close.duckdb")
        store.close()
        assert store._conn is None


class TestLockHelpers:
    def test_execute_and_query(self, tmp_path: Path) -> None:
        store = StoreA(db_path=tmp_path / "helpers.duckdb")
        store.execute_in_lock("INSERT INTO t VALUES (1, 'one')")
        rows = store.query_in_lock("SELECT id, name FROM t WHERE id = ?", [1])
        assert rows == [(1, "one")]
        store.close()

    def test_executemany(self, tmp_path: Path) -> None:
        store = StoreA(db_path=tmp_path / "many.duckdb")
        store.executemany_in_lock(
            "INSERT INTO t VALUES (?, ?)",
            [[1, "a"], [2, "b"], [3, "c"]],
        )
        rows = store.query_in_lock("SELECT COUNT(*) FROM t")
        assert rows == [(3,)]
        store.close()
