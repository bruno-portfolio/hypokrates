"""DuckDB cache store — thread-safe singleton."""

from __future__ import annotations

import asyncio
import contextlib
import json
import logging
import threading
from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING, ClassVar

import duckdb

from hypokrates.cache.migrations import run_migrations
from hypokrates.cache.policies import get_ttl
from hypokrates.config import get_config
from hypokrates.exceptions import CacheError

if TYPE_CHECKING:
    from pathlib import Path

logger = logging.getLogger(__name__)


class CacheStore:
    """Cache DuckDB thread-safe singleton.

    Armazena respostas de API serializadas como JSON com TTL por fonte.
    Usa UPSERT para evitar conflitos de concorrência.
    """

    _instance: ClassVar[CacheStore | None] = None
    _lock: ClassVar[threading.Lock] = threading.Lock()

    def __init__(self, db_path: Path | None = None) -> None:
        if db_path is None:
            cfg = get_config()
            cfg.cache_dir.mkdir(parents=True, exist_ok=True)
            db_path = cfg.cache_dir / "hypokrates_cache.duckdb"

        self._db_path = db_path
        self._conn = duckdb.connect(str(db_path))
        self._db_lock = threading.Lock()
        run_migrations(self._conn)

    @classmethod
    def get_instance(cls) -> CacheStore:
        """Retorna singleton do cache (cria na primeira chamada)."""
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = cls()
        return cls._instance

    @classmethod
    def reset(cls) -> None:
        """Reseta singleton (usado em testes)."""
        with cls._lock:
            if cls._instance is not None:
                cls._instance.close()
                cls._instance = None

    def get(self, key: str) -> dict[str, object] | None:
        """Busca valor no cache. Retorna None se ausente ou expirado."""
        with self._db_lock:
            try:
                result = self._conn.execute(
                    """
                    SELECT data FROM cache_entries
                    WHERE key = ? AND expires_at > CURRENT_TIMESTAMP
                    """,
                    [key],
                ).fetchone()

                if result is None:
                    return None

                # Incrementa hit count
                self._conn.execute(
                    "UPDATE cache_entries SET hit_count = hit_count + 1 WHERE key = ?",
                    [key],
                )

                raw: str = result[0]
                data: dict[str, object] = json.loads(raw)
                return data

            except duckdb.Error as exc:
                logger.warning("Cache read error for key=%s: %s", key, exc)
                return None

    async def aget(self, key: str) -> dict[str, object] | None:
        """Busca valor no cache (async-safe, offloaded to thread pool)."""
        return await asyncio.to_thread(self.get, key)

    def set(self, key: str, data: dict[str, object], source: str) -> None:
        """Armazena valor no cache com TTL baseado na fonte."""
        ttl = get_ttl(source)
        expires_at = datetime.now(UTC) + timedelta(seconds=ttl)
        json_data = json.dumps(data, default=str)

        with self._db_lock:
            try:
                self._conn.execute(
                    "INSERT OR REPLACE INTO cache_entries"
                    " (key, source, data, created_at, expires_at)"
                    " VALUES (?, ?, ?, CURRENT_TIMESTAMP, ?)",
                    [key, source, json_data, expires_at],
                )
            except duckdb.Error as exc:
                raise CacheError(f"Cache write error for key={key}: {exc}") from exc

    async def aset(self, key: str, data: dict[str, object], source: str) -> None:
        """Armazena valor no cache (async-safe, offloaded to thread pool)."""
        await asyncio.to_thread(self.set, key, data, source)

    def invalidate(self, key: str) -> None:
        """Remove entrada específica do cache."""
        with self._db_lock:
            self._conn.execute("DELETE FROM cache_entries WHERE key = ?", [key])

    def clear(self, source: str | None = None) -> int:
        """Limpa cache. Se source fornecido, apenas entradas daquela fonte."""
        with self._db_lock:
            if source:
                result = self._conn.execute("DELETE FROM cache_entries WHERE source = ?", [source])
            else:
                result = self._conn.execute("DELETE FROM cache_entries")
            row = result.fetchone()
            return int(row[0]) if row is not None else 0

    def cleanup_expired(self) -> int:
        """Remove entradas expiradas."""
        with self._db_lock:
            result = self._conn.execute(
                "DELETE FROM cache_entries WHERE expires_at <= CURRENT_TIMESTAMP"
            )
            row = result.fetchone()
            return int(row[0]) if row is not None else 0

    def close(self) -> None:
        """Fecha conexão DuckDB."""
        with self._db_lock, contextlib.suppress(duckdb.Error):
            self._conn.close()
