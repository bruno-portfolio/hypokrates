"""Canada Vigilance DuckDB store — bulk data de farmacovigilância canadense.

Armazena em DuckDB separado. Parse dos arquivos $-delimited acontece 1x;
chamadas subsequentes usam o DuckDB persistido.

Fonte: Canada Vigilance Adverse Reaction Online Database (1965-presente, ~738K reports).
"""

from __future__ import annotations

import logging
import threading
from typing import TYPE_CHECKING, ClassVar

import duckdb

from hypokrates.canada.constants import CANADA_DB_FILENAME

if TYPE_CHECKING:
    from pathlib import Path

logger = logging.getLogger(__name__)

_CREATE_TABLES = """
CREATE TABLE IF NOT EXISTS canada_reports (
    report_id INTEGER PRIMARY KEY,
    date_received VARCHAR DEFAULT '',
    gender_code VARCHAR DEFAULT '',
    age VARCHAR DEFAULT '',
    outcome_code VARCHAR DEFAULT '',
    seriousness_code VARCHAR DEFAULT ''
);

CREATE TABLE IF NOT EXISTS canada_drugs (
    report_drug_id INTEGER,
    report_id INTEGER NOT NULL,
    drug_product_id INTEGER DEFAULT 0,
    drug_role VARCHAR DEFAULT ''
);

CREATE TABLE IF NOT EXISTS canada_reactions (
    reaction_id INTEGER,
    report_id INTEGER NOT NULL,
    pt_name VARCHAR DEFAULT '',
    soc_name VARCHAR DEFAULT '',
    meddra_version VARCHAR DEFAULT ''
);

CREATE TABLE IF NOT EXISTS canada_products (
    drug_product_id INTEGER PRIMARY KEY,
    drug_name VARCHAR DEFAULT ''
);

CREATE TABLE IF NOT EXISTS canada_ingredients (
    drug_product_id INTEGER NOT NULL,
    ingredient_name VARCHAR DEFAULT ''
);

CREATE TABLE IF NOT EXISTS canada_dedup (
    report_id INTEGER PRIMARY KEY,
    is_latest BOOLEAN DEFAULT TRUE
);

CREATE INDEX IF NOT EXISTS idx_canada_drugs_report ON canada_drugs (report_id);
CREATE INDEX IF NOT EXISTS idx_canada_drugs_product ON canada_drugs (drug_product_id);
CREATE INDEX IF NOT EXISTS idx_canada_reactions_report ON canada_reactions (report_id);
CREATE INDEX IF NOT EXISTS idx_canada_reactions_pt ON canada_reactions (UPPER(pt_name));
CREATE INDEX IF NOT EXISTS idx_canada_ingredients_product ON canada_ingredients (drug_product_id);
CREATE INDEX IF NOT EXISTS idx_canada_ingredients_name
    ON canada_ingredients (UPPER(ingredient_name));
"""

_FOUR_COUNTS_SQL = """
WITH drug_reports AS (
    SELECT DISTINCT d.report_id
    FROM canada_drugs d
    JOIN canada_ingredients i ON d.drug_product_id = i.drug_product_id
    WHERE UPPER(i.ingredient_name) = UPPER($1)
    AND ($3 = 'all' OR d.drug_role = 'Suspect')
),
event_reports AS (
    SELECT DISTINCT report_id
    FROM canada_reactions
    WHERE UPPER(pt_name) = UPPER($2)
),
a AS (
    SELECT COUNT(*) AS cnt FROM drug_reports dr
    JOIN event_reports er ON dr.report_id = er.report_id
),
b AS (
    SELECT COUNT(*) AS cnt FROM drug_reports dr
    WHERE dr.report_id NOT IN (SELECT report_id FROM event_reports)
),
c AS (
    SELECT COUNT(*) AS cnt FROM event_reports er
    WHERE er.report_id NOT IN (SELECT report_id FROM drug_reports)
),
total AS (SELECT COUNT(DISTINCT report_id) AS cnt FROM canada_reports)
SELECT
    (SELECT cnt FROM a) AS a_count,
    (SELECT cnt FROM b) AS b_count,
    (SELECT cnt FROM c) AS c_count,
    (SELECT cnt FROM total) AS total_count
"""

_TOP_EVENTS_SQL = """
SELECT r.pt_name, COUNT(DISTINCT r.report_id) AS cnt
FROM canada_reactions r
JOIN canada_drugs d ON r.report_id = d.report_id
JOIN canada_ingredients i ON d.drug_product_id = i.drug_product_id
WHERE UPPER(i.ingredient_name) = UPPER($1)
AND ($2 = 'all' OR d.drug_role = 'Suspect')
AND r.pt_name != ''
GROUP BY r.pt_name
ORDER BY cnt DESC
LIMIT $3
"""


class CanadaVigilanceStore:
    """Store DuckDB para dados do Canada Vigilance.

    Singleton thread-safe. Persiste em ``~/.cache/hypokrates/canada_vigilance.duckdb``.
    """

    _instance: ClassVar[CanadaVigilanceStore | None] = None
    _lock: ClassVar[threading.Lock] = threading.Lock()

    def __init__(self, db_path: Path | None = None) -> None:
        if db_path is None:
            from hypokrates.config import get_config

            db_path = get_config().cache_dir / CANADA_DB_FILENAME
        db_path.parent.mkdir(parents=True, exist_ok=True)
        self._db_path = db_path
        self._conn = duckdb.connect(str(db_path))
        self._db_lock = threading.Lock()
        self._conn.execute(_CREATE_TABLES)
        self._loaded = self._check_loaded()

    @classmethod
    def get_instance(cls) -> CanadaVigilanceStore:
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
        """Se o store contém dados carregados."""
        return self._loaded

    def _check_loaded(self) -> bool:
        """Verifica se já existem dados no store."""
        result = self._conn.execute("SELECT COUNT(*) FROM canada_reports").fetchone()
        return result is not None and result[0] > 0

    def load_from_csvs(self, csv_dir: str) -> int:
        """Carrega arquivos $-delimited do Canada Vigilance.

        Args:
            csv_dir: Diretório contendo os arquivos extraídos do ZIP.

        Returns:
            Número de reports carregados.
        """
        from hypokrates.canada.parser import load_files_to_store

        count = load_files_to_store(self, csv_dir)
        self._loaded = True
        return count

    def four_counts(
        self, drug: str, event: str, *, suspect_only: bool = False
    ) -> tuple[int, int, int, int]:
        """Retorna (a, b, c, n) para cálculo de PRR.

        a = drug + event
        b = drug + NOT event
        c = NOT drug + event
        n = total reports
        """
        role = "suspect" if suspect_only else "all"
        with self._db_lock:
            row = self._conn.execute(_FOUR_COUNTS_SQL, [drug, event, role]).fetchone()

        if row is None:
            return 0, 0, 0, 0

        a_count = int(row[0])
        b_count = int(row[1])
        c_count = int(row[2])
        n_count = int(row[3])
        return a_count, b_count, c_count, n_count

    def top_events(
        self,
        drug: str,
        *,
        suspect_only: bool = False,
        limit: int = 10,
    ) -> list[tuple[str, int]]:
        """Retorna top eventos adversos para uma droga.

        Returns:
            Lista de (event_term, count).
        """
        role = "suspect" if suspect_only else "all"
        with self._db_lock:
            rows = self._conn.execute(_TOP_EVENTS_SQL, [drug, role, limit]).fetchall()

        return [(row[0], int(row[1])) for row in rows]

    def count_reports(self) -> int:
        """Total de reports no store."""
        with self._db_lock:
            result = self._conn.execute("SELECT COUNT(*) FROM canada_reports").fetchone()
        return result[0] if result else 0

    def count_drugs(self) -> int:
        """Total de drug records."""
        with self._db_lock:
            result = self._conn.execute("SELECT COUNT(*) FROM canada_drugs").fetchone()
        return result[0] if result else 0

    def count_reactions(self) -> int:
        """Total de reaction records."""
        with self._db_lock:
            result = self._conn.execute("SELECT COUNT(*) FROM canada_reactions").fetchone()
        return result[0] if result else 0

    def date_range(self) -> str:
        """Range de datas dos reports."""
        with self._db_lock:
            result = self._conn.execute(
                "SELECT MIN(date_received), MAX(date_received) "
                "FROM canada_reports WHERE date_received != ''"
            ).fetchone()
        if result and result[0] and result[1]:
            return f"{result[0]} to {result[1]}"
        return ""

    def execute_in_lock(self, sql: str, params: list[object] | None = None) -> None:
        """Executa SQL dentro do lock."""
        with self._db_lock:
            if params:
                self._conn.execute(sql, params)
            else:
                self._conn.execute(sql)

    def executemany_in_lock(self, sql: str, rows: list[list[object]]) -> None:
        """Executa SQL com múltiplas linhas dentro do lock."""
        with self._db_lock:
            self._conn.executemany(sql, rows)

    def close(self) -> None:
        """Fecha a conexão DuckDB."""
        with self._db_lock:
            if self._conn is not None:
                self._conn.close()
                self._conn = None  # type: ignore[assignment]
