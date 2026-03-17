"""JADER DuckDB store — farmacovigilância japonesa (PMDA).

Armazena em DuckDB separado. Parse dos CSVs cp932 acontece 1x;
chamadas subsequentes usam o DuckDB persistido.

Fonte: JADER (2004-presente, ~970K reports).
"""

from __future__ import annotations

import logging
import threading
from typing import TYPE_CHECKING, ClassVar

import duckdb

from hypokrates.jader.constants import JADER_DB_FILENAME

if TYPE_CHECKING:
    from pathlib import Path

logger = logging.getLogger(__name__)

_CREATE_TABLES = """
CREATE TABLE IF NOT EXISTS jader_demo (
    case_id VARCHAR NOT NULL,
    report_version INTEGER DEFAULT 1,
    sex VARCHAR DEFAULT '',
    age_group VARCHAR DEFAULT '',
    weight VARCHAR DEFAULT '',
    reporter_qual VARCHAR DEFAULT ''
);

CREATE TABLE IF NOT EXISTS jader_drug (
    case_id VARCHAR NOT NULL,
    report_version INTEGER DEFAULT 1,
    drug_name_jp VARCHAR DEFAULT '',
    drug_name_en VARCHAR DEFAULT '',
    drug_confidence VARCHAR DEFAULT 'unmapped',
    brand_name_jp VARCHAR DEFAULT '',
    drug_role VARCHAR DEFAULT ''
);

CREATE TABLE IF NOT EXISTS jader_reac (
    case_id VARCHAR NOT NULL,
    report_version INTEGER DEFAULT 1,
    pt_jp VARCHAR DEFAULT '',
    pt_en VARCHAR DEFAULT '',
    event_confidence VARCHAR DEFAULT 'unmapped',
    outcome VARCHAR DEFAULT ''
);

CREATE TABLE IF NOT EXISTS jader_dedup (
    case_id VARCHAR PRIMARY KEY,
    report_version INTEGER NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_jader_drug_en ON jader_drug (UPPER(drug_name_en));
CREATE INDEX IF NOT EXISTS idx_jader_reac_en ON jader_reac (UPPER(pt_en));
CREATE INDEX IF NOT EXISTS idx_jader_drug_case ON jader_drug (case_id);
CREATE INDEX IF NOT EXISTS idx_jader_reac_case ON jader_reac (case_id);
"""

_FOUR_COUNTS_SQL = """
WITH drug_reports AS (
    SELECT DISTINCT d.case_id
    FROM jader_drug d
    INNER JOIN jader_dedup dd ON d.case_id = dd.case_id
        AND d.report_version = dd.report_version
    WHERE UPPER(d.drug_name_en) = UPPER($1)
    AND ($3 = 'all' OR d.drug_role = '被疑薬')
),
event_reports AS (
    SELECT DISTINCT r.case_id
    FROM jader_reac r
    INNER JOIN jader_dedup dd ON r.case_id = dd.case_id
        AND r.report_version = dd.report_version
    WHERE UPPER(r.pt_en) = UPPER($2)
),
a AS (
    SELECT COUNT(*) AS cnt FROM drug_reports dr
    JOIN event_reports er ON dr.case_id = er.case_id
),
b AS (
    SELECT COUNT(*) AS cnt FROM drug_reports dr
    WHERE dr.case_id NOT IN (SELECT case_id FROM event_reports)
),
c AS (
    SELECT COUNT(*) AS cnt FROM event_reports er
    WHERE er.case_id NOT IN (SELECT case_id FROM drug_reports)
),
total AS (SELECT COUNT(*) AS cnt FROM jader_dedup)
SELECT
    (SELECT cnt FROM a) AS a_count,
    (SELECT cnt FROM b) AS b_count,
    (SELECT cnt FROM c) AS c_count,
    (SELECT cnt FROM total) AS total_count
"""

_TOP_EVENTS_SQL = """
SELECT r.pt_en, COUNT(DISTINCT r.case_id) AS cnt
FROM jader_reac r
INNER JOIN jader_dedup dd ON r.case_id = dd.case_id
    AND r.report_version = dd.report_version
INNER JOIN jader_drug d ON r.case_id = d.case_id
    AND r.report_version = d.report_version
WHERE UPPER(d.drug_name_en) = UPPER($1)
AND ($2 = 'all' OR d.drug_role = '被疑薬')
AND r.pt_en != ''
GROUP BY r.pt_en
ORDER BY cnt DESC
LIMIT $3
"""


class JADERStore:
    """Store DuckDB para dados do JADER.

    Singleton thread-safe. Persiste em ``~/.cache/hypokrates/jader.duckdb``.
    """

    _instance: ClassVar[JADERStore | None] = None
    _lock: ClassVar[threading.Lock] = threading.Lock()

    def __init__(self, db_path: Path | None = None) -> None:
        if db_path is None:
            from hypokrates.config import get_config

            db_path = get_config().cache_dir / JADER_DB_FILENAME
        db_path.parent.mkdir(parents=True, exist_ok=True)
        self._db_path = db_path
        self._conn = duckdb.connect(str(db_path))
        self._db_lock = threading.Lock()
        self._conn.execute(_CREATE_TABLES)
        self._loaded = self._check_loaded()

    @classmethod
    def get_instance(cls) -> JADERStore:
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
        for table in ("jader_demo", "jader_drug", "jader_reac"):
            result = self._conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()
            if result is None or result[0] == 0:
                return False
        return True

    def load_from_csvs(self, csv_dir: str) -> int:
        """Carrega CSVs cp932 do JADER.

        Returns:
            Número de reports carregados.
        """
        from hypokrates.jader.parser import load_files_to_store

        count = load_files_to_store(self, csv_dir)
        self._loaded = True
        return count

    def four_counts(
        self, drug: str, event: str, *, suspect_only: bool = False
    ) -> tuple[int, int, int, int]:
        """Retorna (a, b, c, n) para cálculo de PRR."""
        role = "suspect" if suspect_only else "all"
        with self._db_lock:
            row = self._conn.execute(_FOUR_COUNTS_SQL, [drug, event, role]).fetchone()

        if row is None:
            return 0, 0, 0, 0

        return int(row[0]), int(row[1]), int(row[2]), int(row[3])

    def top_events(
        self,
        drug: str,
        *,
        suspect_only: bool = False,
        limit: int = 10,
    ) -> list[tuple[str, int]]:
        """Retorna top eventos adversos para uma droga."""
        role = "suspect" if suspect_only else "all"
        with self._db_lock:
            rows = self._conn.execute(_TOP_EVENTS_SQL, [drug, role, limit]).fetchall()

        return [(row[0], int(row[1])) for row in rows]

    def count_reports(self) -> int:
        """Total de reports (deduplicated)."""
        with self._db_lock:
            result = self._conn.execute("SELECT COUNT(*) FROM jader_dedup").fetchone()
        return result[0] if result else 0

    def count_drugs(self) -> int:
        """Total de drug records."""
        with self._db_lock:
            result = self._conn.execute("SELECT COUNT(*) FROM jader_drug").fetchone()
        return result[0] if result else 0

    def count_reactions(self) -> int:
        """Total de reaction records."""
        with self._db_lock:
            result = self._conn.execute("SELECT COUNT(*) FROM jader_reac").fetchone()
        return result[0] if result else 0

    def date_range(self) -> str:
        """Range de case_ids (proxy for date range, JADER usa IDs sequenciais)."""
        with self._db_lock:
            result = self._conn.execute(
                "SELECT MIN(case_id), MAX(case_id) FROM jader_dedup"
            ).fetchone()
        if result and result[0] and result[1]:
            return f"{result[0]} to {result[1]}"
        return ""

    def mapping_stats(self) -> dict[str, int]:
        """Estatísticas de mapeamento JP→EN."""
        with self._db_lock:
            drug_stats = self._conn.execute(
                "SELECT drug_confidence, COUNT(*) FROM jader_drug GROUP BY drug_confidence"
            ).fetchall()
            event_stats = self._conn.execute(
                "SELECT event_confidence, COUNT(*) FROM jader_reac GROUP BY event_confidence"
            ).fetchall()

        stats: dict[str, int] = {
            "exact_drugs": 0,
            "inferred_drugs": 0,
            "unmapped_drugs": 0,
            "exact_events": 0,
            "inferred_events": 0,
            "unmapped_events": 0,
        }
        for conf, cnt in drug_stats:
            key = f"{conf}_drugs"
            if key in stats:
                stats[key] = int(cnt)
        for conf, cnt in event_stats:
            key = f"{conf}_events"
            if key in stats:
                stats[key] = int(cnt)
        return stats

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

    def close(self) -> None:
        """Fecha a conexão DuckDB."""
        with self._db_lock:
            if self._conn is not None:
                self._conn.close()
                self._conn = None  # type: ignore[assignment]
