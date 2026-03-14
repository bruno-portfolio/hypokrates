"""Schema migrations para o DuckDB cache."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    import duckdb

MIGRATIONS: list[str] = [
    # v1: tabela inicial de cache
    """
    CREATE TABLE IF NOT EXISTS cache_entries (
        key VARCHAR PRIMARY KEY,
        source VARCHAR NOT NULL,
        data JSON NOT NULL,
        created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
        expires_at TIMESTAMP NOT NULL,
        hit_count INTEGER NOT NULL DEFAULT 0
    )
    """,
]


def run_migrations(conn: duckdb.DuckDBPyConnection) -> None:
    """Executa todas as migrations pendentes."""
    for sql in MIGRATIONS:
        conn.execute(sql)
