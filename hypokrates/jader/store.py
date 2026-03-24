"""JADER DuckDB store — farmacovigilância japonesa (PMDA).

Armazena em DuckDB separado. Parse dos CSVs cp932 acontece 1x;
chamadas subsequentes usam o DuckDB persistido.

Fonte: JADER (2004-presente, ~970K reports).
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from hypokrates.jader.constants import JADER_DB_FILENAME
from hypokrates.store.base import BaseDuckDBStore

if TYPE_CHECKING:
    from pathlib import Path

logger = logging.getLogger(__name__)

_CREATE_TABLES_SQL = """
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
    WHERE list_contains($drugs, UPPER(d.drug_name_en))
    AND ($role = 'all' OR d.drug_role = '被疑薬')
),
event_reports AS (
    SELECT DISTINCT r.case_id
    FROM jader_reac r
    INNER JOIN jader_dedup dd ON r.case_id = dd.case_id
        AND r.report_version = dd.report_version
    WHERE list_contains($events, UPPER(r.pt_en))
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
WHERE list_contains($drugs, UPPER(d.drug_name_en))
AND ($role = 'all' OR d.drug_role = '被疑薬')
AND r.pt_en != ''
GROUP BY r.pt_en
ORDER BY cnt DESC
LIMIT $limit
"""


class JADERStore(BaseDuckDBStore):
    """Store DuckDB para dados do JADER.

    Singleton thread-safe. Persiste em ``~/.cache/hypokrates/jader.duckdb``.
    """

    _DB_FILENAME = JADER_DB_FILENAME
    _CREATE_TABLES = _CREATE_TABLES_SQL

    def __init__(self, db_path: Path | None = None) -> None:
        super().__init__(db_path)
        self._loaded = self._check_loaded()

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
        self, drug_names: list[str], event_terms: list[str], *, suspect_only: bool = False
    ) -> tuple[int, int, int, int]:
        """Retorna (a, b, c, n) para cálculo de PRR."""
        role = "suspect" if suspect_only else "all"
        with self._db_lock:
            row = self._conn.execute(
                _FOUR_COUNTS_SQL,
                {"drugs": drug_names, "events": event_terms, "role": role},
            ).fetchone()

        if row is None:
            return 0, 0, 0, 0

        return int(row[0]), int(row[1]), int(row[2]), int(row[3])

    def top_events(
        self,
        drug_names: list[str],
        *,
        suspect_only: bool = False,
        limit: int = 10,
    ) -> list[tuple[str, int]]:
        """Retorna top eventos adversos para uma droga."""
        role = "suspect" if suspect_only else "all"
        with self._db_lock:
            rows = self._conn.execute(
                _TOP_EVENTS_SQL, {"drugs": drug_names, "role": role, "limit": limit}
            ).fetchall()

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
