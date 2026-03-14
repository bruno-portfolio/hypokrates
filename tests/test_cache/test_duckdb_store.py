"""Testes para hypokrates.cache.duckdb_store — CRUD, TTL, integridade de dados."""

from __future__ import annotations

from typing import TYPE_CHECKING

from hypokrates.cache.duckdb_store import CacheStore

if TYPE_CHECKING:
    from pathlib import Path


class TestCacheStoreContract:
    """CRUD básico — contrato de cache."""

    def test_set_and_get(self, tmp_cache: CacheStore) -> None:
        data = {"key": "value", "count": 42}
        tmp_cache.set("test:key", data, "faers")
        result = tmp_cache.get("test:key")
        assert result is not None
        assert result["key"] == "value"
        assert result["count"] == 42

    def test_get_missing_key_returns_none(self, tmp_cache: CacheStore) -> None:
        result = tmp_cache.get("nonexistent:key")
        assert result is None

    def test_invalidate_removes_entry(self, tmp_cache: CacheStore) -> None:
        tmp_cache.set("test:remove", {"data": 1}, "faers")
        tmp_cache.invalidate("test:remove")
        assert tmp_cache.get("test:remove") is None

    def test_upsert_overwrites(self, tmp_cache: CacheStore) -> None:
        tmp_cache.set("test:upsert", {"version": 1}, "faers")
        tmp_cache.set("test:upsert", {"version": 2}, "faers")
        result = tmp_cache.get("test:upsert")
        assert result is not None
        assert result["version"] == 2

    def test_close_and_reopen(self, tmp_path: Path) -> None:
        db_path = tmp_path / "reopen.duckdb"
        store = CacheStore(db_path)
        store.set("persist:key", {"persisted": True}, "faers")
        store.close()

        store2 = CacheStore(db_path)
        result = store2.get("persist:key")
        assert result is not None
        assert result["persisted"] is True
        store2.close()

    def test_clear_all(self, tmp_cache: CacheStore) -> None:
        tmp_cache.set("k1", {"a": 1}, "faers")
        tmp_cache.set("k2", {"b": 2}, "faers")
        tmp_cache.clear()
        assert tmp_cache.get("k1") is None
        assert tmp_cache.get("k2") is None

    def test_clear_by_source(self, tmp_cache: CacheStore) -> None:
        tmp_cache.set("k1", {"a": 1}, "faers")
        tmp_cache.set("k2", {"b": 2}, "other_source")
        tmp_cache.clear("faers")
        assert tmp_cache.get("k1") is None
        # other_source entry should remain
        result = tmp_cache.get("k2")
        assert result is not None

    def test_multiple_keys(self, tmp_cache: CacheStore) -> None:
        for i in range(10):
            tmp_cache.set(f"test:key:{i}", {"index": i}, "faers")
        for i in range(10):
            result = tmp_cache.get(f"test:key:{i}")
            assert result is not None
            assert result["index"] == i


class TestCacheTTL:
    """TTL expira corretamente."""

    def test_expired_entry_returns_none(self, tmp_path: Path) -> None:
        """Set com TTL muito curto (via source com TTL=1s), sleep, get → None."""
        db_path = tmp_path / "ttl_test.duckdb"
        store = CacheStore(db_path)

        # Inserir diretamente com expiração no passado usando SQL
        import json
        from datetime import UTC, datetime, timedelta

        key = "test:expired"
        data = json.dumps({"expired": True})
        expires_at = datetime.now(UTC) - timedelta(seconds=1)

        store._conn.execute(
            """
            INSERT OR REPLACE INTO cache_entries (key, source, data, created_at, expires_at)
            VALUES (?, ?, ?, CURRENT_TIMESTAMP, ?)
            """,
            [key, "faers", data, expires_at],
        )

        result = store.get(key)
        assert result is None
        store.close()

    def test_non_expired_entry_returns_data(self, tmp_cache: CacheStore) -> None:
        tmp_cache.set("test:valid", {"valid": True}, "faers")
        # Imediatamente após set, deve retornar (TTL=24h)
        result = tmp_cache.get("test:valid")
        assert result is not None
        assert result["valid"] is True

    def test_cleanup_expired_removes_old_entries(self, tmp_path: Path) -> None:
        import json
        from datetime import UTC, datetime, timedelta

        db_path = tmp_path / "cleanup_test.duckdb"
        store = CacheStore(db_path)

        # Inserir uma entrada expirada
        expires_at = datetime.now(UTC) - timedelta(seconds=1)
        store._conn.execute(
            """
            INSERT OR REPLACE INTO cache_entries (key, source, data, created_at, expires_at)
            VALUES (?, ?, ?, CURRENT_TIMESTAMP, ?)
            """,
            ["expired:key", "faers", json.dumps({"old": True}), expires_at],
        )

        # Inserir uma válida
        store.set("valid:key", {"new": True}, "faers")

        store.cleanup_expired()
        assert store.get("expired:key") is None
        assert store.get("valid:key") is not None
        store.close()


class TestCacheDataIntegrity:
    """Dados sobrevivem round-trip JSON sem corrupção."""

    def test_preserves_nested_dicts(self, tmp_cache: CacheStore) -> None:
        data = {"level1": {"level2": {"level3": "deep"}}}
        tmp_cache.set("test:nested", data, "faers")
        result = tmp_cache.get("test:nested")
        assert result is not None
        assert result["level1"]["level2"]["level3"] == "deep"  # type: ignore[index]

    def test_preserves_lists(self, tmp_cache: CacheStore) -> None:
        data = {"items": [1, 2, 3, "four", None]}
        tmp_cache.set("test:list", data, "faers")
        result = tmp_cache.get("test:list")
        assert result is not None
        assert result["items"] == [1, 2, 3, "four", None]

    def test_preserves_unicode(self, tmp_cache: CacheStore) -> None:
        data = {"name": "propoföl", "japanese": "プロポフォール", "emoji": "✓"}
        tmp_cache.set("test:unicode", data, "faers")
        result = tmp_cache.get("test:unicode")
        assert result is not None
        assert result["name"] == "propoföl"
        assert result["japanese"] == "プロポフォール"

    def test_preserves_null_values(self, tmp_cache: CacheStore) -> None:
        data = {"present": "yes", "absent": None}
        tmp_cache.set("test:null", data, "faers")
        result = tmp_cache.get("test:null")
        assert result is not None
        assert result["present"] == "yes"
        assert result["absent"] is None

    def test_preserves_numeric_types(self, tmp_cache: CacheStore) -> None:
        """int e float preservados (JSON não distingue, mas Python sim)."""
        data = {"integer": 42, "floating": 3.14, "zero": 0, "negative": -1}
        tmp_cache.set("test:numbers", data, "faers")
        result = tmp_cache.get("test:numbers")
        assert result is not None
        assert result["integer"] == 42
        assert result["floating"] == 3.14
        assert result["zero"] == 0
        assert result["negative"] == -1

    def test_preserves_boolean_values(self, tmp_cache: CacheStore) -> None:
        data = {"yes": True, "no": False}
        tmp_cache.set("test:bool", data, "faers")
        result = tmp_cache.get("test:bool")
        assert result is not None
        assert result["yes"] is True
        assert result["no"] is False

    def test_preserves_empty_structures(self, tmp_cache: CacheStore) -> None:
        data = {"empty_list": [], "empty_dict": {}, "empty_string": ""}
        tmp_cache.set("test:empty", data, "faers")
        result = tmp_cache.get("test:empty")
        assert result is not None
        assert result["empty_list"] == []
        assert result["empty_dict"] == {}
        assert result["empty_string"] == ""

    def test_large_data(self, tmp_cache: CacheStore) -> None:
        """Dados grandes sobrevivem round-trip."""
        data = {"results": [{"term": f"TERM_{i}", "count": i} for i in range(1000)]}
        tmp_cache.set("test:large", data, "faers")
        result = tmp_cache.get("test:large")
        assert result is not None
        assert len(result["results"]) == 1000  # type: ignore[arg-type]
