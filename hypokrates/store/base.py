"""Base class para DuckDB bulk stores — singleton, lock, close."""

from __future__ import annotations

import threading
from typing import TYPE_CHECKING, ClassVar, Self

import duckdb

if TYPE_CHECKING:
    from pathlib import Path


class BaseDuckDBStore:
    """Base para stores DuckDB com singleton thread-safe.

    Subclasses devem definir:
        _DB_FILENAME: str — nome do arquivo DuckDB
        _CREATE_TABLES: str — SQL de criação de tabelas
    """

    _DB_FILENAME: ClassVar[str]
    _CREATE_TABLES: ClassVar[str]
    _instance: ClassVar[BaseDuckDBStore | None] = None
    _lock: ClassVar[threading.Lock] = threading.Lock()

    def __init_subclass__(cls, **kwargs: object) -> None:  # noqa: D105
        super().__init_subclass__(**kwargs)
        cls._instance = None
        cls._lock = threading.Lock()

    def __init__(self, db_path: Path | None = None) -> None:
        if db_path is None:
            from hypokrates.config import get_config

            db_path = get_config().cache_dir / self._DB_FILENAME
        db_path.parent.mkdir(parents=True, exist_ok=True)
        self._db_path = db_path
        self._conn = duckdb.connect(str(db_path))
        self._db_lock = threading.Lock()
        self._conn.execute(self._CREATE_TABLES)

    @classmethod
    def get_instance(cls) -> Self:
        """Retorna (ou cria) singleton."""
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = cls()
        return cls._instance  # type: ignore[return-value]

    @classmethod
    def reset(cls) -> None:
        """Reseta singleton (usado em testes)."""
        with cls._lock:
            if cls._instance is not None:
                cls._instance.close()
                cls._instance = None

    def close(self) -> None:
        """Fecha a conexão DuckDB."""
        with self._db_lock:
            if self._conn is not None:
                self._conn.close()
                self._conn = None  # type: ignore[assignment]

    def execute_in_lock(self, sql: str, params: list[object] | None = None) -> None:
        """Executa SQL dentro do lock."""
        with self._db_lock:
            if params:
                self._conn.execute(sql, params)
            else:
                self._conn.execute(sql)

    def query_in_lock(
        self,
        sql: str,
        params: list[object] | None = None,
    ) -> list[tuple[object, ...]]:
        """Executa SQL dentro do lock e retorna resultado."""
        with self._db_lock:
            if params:
                return self._conn.execute(sql, params).fetchall()
            return self._conn.execute(sql).fetchall()

    def executemany_in_lock(self, sql: str, rows: list[list[object]]) -> None:
        """Executa SQL com múltiplas linhas dentro do lock."""
        with self._db_lock:
            self._conn.executemany(sql, rows)
