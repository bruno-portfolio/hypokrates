"""ANVISA DuckDB store — indexa medicamentos registrados para busca rapida.

Armazena em DuckDB separado do cache HTTP para evitar lock contention.
Parse do CSV acontece 1x; chamadas subsequentes usam o DuckDB persistido.
"""

from __future__ import annotations

import logging
import threading
from datetime import UTC, datetime
from typing import TYPE_CHECKING, ClassVar

import duckdb

from hypokrates.anvisa.constants import ANVISA_DB_FILENAME, NOME_EN_PT, NOME_PT_EN
from hypokrates.anvisa.models import AnvisaMedicamento, AnvisaNomeMapping, AnvisaSearchResult
from hypokrates.anvisa.parser import (
    normalize_text,
    parse_medicamentos_csv,
    split_apresentacoes,
    split_substancias,
)

if TYPE_CHECKING:
    from pathlib import Path

logger = logging.getLogger(__name__)

_CREATE_TABLES = """
CREATE TABLE IF NOT EXISTS anvisa_medicamentos (
    registro VARCHAR PRIMARY KEY,
    nome_produto VARCHAR NOT NULL,
    substancias VARCHAR NOT NULL DEFAULT '',
    categoria VARCHAR NOT NULL DEFAULT '',
    referencia VARCHAR DEFAULT '',
    atc VARCHAR DEFAULT '',
    tarja VARCHAR DEFAULT '',
    complemento VARCHAR DEFAULT '',
    empresa VARCHAR DEFAULT '',
    substancias_norm VARCHAR DEFAULT '',
    image_url VARCHAR DEFAULT NULL
);

CREATE TABLE IF NOT EXISTS anvisa_name_index (
    name_norm VARCHAR NOT NULL,
    registro VARCHAR NOT NULL,
    tipo VARCHAR NOT NULL DEFAULT 'produto'
);

CREATE INDEX IF NOT EXISTS idx_anvisa_name ON anvisa_name_index (name_norm);

CREATE TABLE IF NOT EXISTS anvisa_nome_mapping (
    nome_pt VARCHAR NOT NULL,
    nome_en VARCHAR NOT NULL,
    PRIMARY KEY (nome_pt, nome_en)
);

CREATE TABLE IF NOT EXISTS anvisa_meta (
    key VARCHAR PRIMARY KEY,
    value VARCHAR NOT NULL
);
"""


class AnvisaStore:
    """Store DuckDB para dados da ANVISA.

    Singleton thread-safe. Persiste em ``~/.cache/hypokrates/anvisa.duckdb``.
    """

    _instance: ClassVar[AnvisaStore | None] = None
    _lock: ClassVar[threading.Lock] = threading.Lock()

    def __init__(self, db_path: Path | None = None) -> None:
        if db_path is None:
            from hypokrates.config import get_config

            db_path = get_config().cache_dir / ANVISA_DB_FILENAME
        db_path.parent.mkdir(parents=True, exist_ok=True)
        self._db_path = db_path
        self._conn = duckdb.connect(str(db_path))
        self._db_lock = threading.Lock()
        self._conn.execute(_CREATE_TABLES)
        self._loaded = self._check_loaded()

    @classmethod
    def get_instance(cls) -> AnvisaStore:
        """Retorna (ou cria) singleton."""
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

    @property
    def loaded(self) -> bool:
        """Se o store contem dados carregados."""
        return self._loaded

    def _check_loaded(self) -> bool:
        result = self._conn.execute("SELECT COUNT(*) FROM anvisa_medicamentos").fetchone()
        return result is not None and result[0] > 0

    def get_loaded_at(self) -> str | None:
        """Retorna timestamp de quando os dados foram carregados."""
        with self._db_lock:
            row = self._conn.execute(
                "SELECT value FROM anvisa_meta WHERE key = 'loaded_at'"
            ).fetchone()
            return row[0] if row else None

    def load_from_csv(self, csv_path: str | Path) -> int:
        """Carrega dados do CSV da ANVISA para o DuckDB."""
        logger.info("Loading ANVISA CSV: %s", csv_path)
        rows = parse_medicamentos_csv(csv_path)

        if not rows:
            logger.warning("No medicamentos found in CSV")
            return 0

        with self._db_lock:
            self._conn.execute("DELETE FROM anvisa_name_index")
            self._conn.execute("DELETE FROM anvisa_medicamentos")
            self._conn.execute("DELETE FROM anvisa_nome_mapping")

            self._batch_insert(rows)
            self._load_nome_mapping()

            now = datetime.now(UTC).isoformat()
            self._conn.execute(
                "INSERT OR REPLACE INTO anvisa_meta VALUES ('loaded_at', ?)",
                [now],
            )

        self._loaded = True
        logger.info("ANVISA loaded: %d medicamentos", len(rows))
        return len(rows)

    def _batch_insert(self, rows: list[dict[str, object]]) -> None:
        med_rows: list[list[object]] = []
        name_rows: list[list[str]] = []

        for row in rows:
            registro = str(row["registro"])
            nome = str(row["nome_produto"])
            substancias_raw = str(row["substancias"])

            med_rows.append(
                [
                    registro,
                    nome,
                    substancias_raw,
                    str(row["categoria"]),
                    str(row["referencia"]),
                    str(row["atc"]),
                    str(row["tarja"]),
                    str(row["complemento"]),
                    str(row["empresa"]),
                    str(row["substancias_norm"]),
                    None,  # image_url
                ]
            )

            nome_norm = normalize_text(nome)
            if nome_norm:
                name_rows.append([nome_norm, registro, "produto"])

            for sub in split_substancias(substancias_raw):
                sub_norm = normalize_text(sub)
                if sub_norm:
                    name_rows.append([sub_norm, registro, "substancia"])

        if med_rows:
            placeholders = ", ".join(["?"] * 11)
            self._conn.executemany(
                f"INSERT OR REPLACE INTO anvisa_medicamentos VALUES ({placeholders})",
                med_rows,
            )
        if name_rows:
            self._conn.executemany(
                "INSERT INTO anvisa_name_index VALUES (?, ?, ?)",
                name_rows,
            )

    def _load_nome_mapping(self) -> None:
        mapping_rows = [[normalize_text(pt), en.upper()] for pt, en in NOME_PT_EN.items()]
        if mapping_rows:
            self._conn.executemany(
                "INSERT OR REPLACE INTO anvisa_nome_mapping VALUES (?, ?)",
                mapping_rows,
            )

    def search(
        self,
        query: str,
        *,
        limit: int = 20,
    ) -> AnvisaSearchResult:
        """Busca por nome ou substancia (accent-insensitive, partial match)."""
        query_norm = normalize_text(query)
        if not query_norm:
            return AnvisaSearchResult(query=query, total=0)

        mapped_norm = self._try_en_to_pt(query_norm)
        search_terms = [query_norm]
        if mapped_norm and mapped_norm != query_norm:
            search_terms.append(mapped_norm)

        with self._db_lock:
            registros: set[str] = set()
            for term in search_terms:
                rows = self._conn.execute(
                    "SELECT DISTINCT registro FROM anvisa_name_index "
                    "WHERE name_norm LIKE ? LIMIT ?",
                    [f"%{term}%", limit * 2],
                ).fetchall()
                for row in rows:
                    registros.add(row[0])

            medicamentos = self._fetch_medicamentos(registros, limit)

        return AnvisaSearchResult(
            query=query,
            medicamentos=medicamentos,
            total=len(medicamentos),
        )

    def search_by_substancia(
        self,
        substancia: str,
        *,
        categoria: str | None = None,
        limit: int = 50,
    ) -> AnvisaSearchResult:
        """Busca por substancia ativa, opcionalmente filtra por categoria."""
        sub_norm = normalize_text(substancia)
        if not sub_norm:
            return AnvisaSearchResult(query=substancia, total=0)

        mapped = self._try_en_to_pt(sub_norm)
        search_terms = [sub_norm]
        if mapped and mapped != sub_norm:
            search_terms.append(mapped)

        with self._db_lock:
            registros: set[str] = set()
            for term in search_terms:
                rows = self._conn.execute(
                    "SELECT DISTINCT registro FROM anvisa_name_index "
                    "WHERE name_norm LIKE ? AND tipo = 'substancia' LIMIT ?",
                    [f"%{term}%", limit * 2],
                ).fetchall()
                for row in rows:
                    registros.add(row[0])

            medicamentos = self._fetch_medicamentos(registros, limit)

        if categoria:
            cat_upper = categoria.upper()
            medicamentos = [m for m in medicamentos if cat_upper in m.categoria.upper()]

        return AnvisaSearchResult(
            query=substancia,
            medicamentos=medicamentos,
            total=len(medicamentos),
        )

    def map_nome(self, nome: str) -> AnvisaNomeMapping | None:
        """Mapeia nome PT<->EN."""
        nome_norm = normalize_text(nome)
        if not nome_norm:
            return None

        with self._db_lock:
            row = self._conn.execute(
                "SELECT nome_en FROM anvisa_nome_mapping WHERE nome_pt = ?",
                [nome_norm],
            ).fetchone()
            if row:
                return AnvisaNomeMapping(nome_pt=nome_norm, nome_en=row[0], source="static")

            row = self._conn.execute(
                "SELECT nome_pt FROM anvisa_nome_mapping WHERE nome_en = ?",
                [nome_norm],
            ).fetchone()
            if row:
                return AnvisaNomeMapping(nome_pt=row[0], nome_en=nome_norm, source="static")

        return None

    def _try_en_to_pt(self, nome_norm: str) -> str | None:
        en_upper = nome_norm.upper()
        pt = NOME_EN_PT.get(en_upper)
        if pt:
            return normalize_text(pt)
        return None

    def _fetch_medicamentos(self, registros: set[str], limit: int) -> list[AnvisaMedicamento]:
        if not registros:
            return []

        placeholders = ", ".join(["?"] * min(len(registros), limit))
        reg_list = list(registros)[:limit]

        rows = self._conn.execute(
            f"SELECT * FROM anvisa_medicamentos WHERE registro IN ({placeholders})",
            reg_list,
        ).fetchall()

        return [
            AnvisaMedicamento(
                registro=row[0],
                nome_produto=row[1],
                substancias=split_substancias(row[2]),
                categoria=row[3],
                referencia=row[4],
                atc=row[5],
                tarja=row[6],
                apresentacoes=split_apresentacoes(row[7]),
                empresa=row[8],
                image_url=row[10],
            )
            for row in rows
        ]

    def close(self) -> None:
        """Fecha a conexao DuckDB."""
        with self._db_lock:
            if self._conn is not None:
                self._conn.close()
                self._conn = None  # type: ignore[assignment]
