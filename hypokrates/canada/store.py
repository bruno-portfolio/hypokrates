"""Canada Vigilance DuckDB store — bulk data de farmacovigilância canadense.

Armazena em DuckDB separado. Parse dos arquivos $-delimited acontece 1x;
chamadas subsequentes usam o DuckDB persistido.

Fonte: Canada Vigilance Adverse Reaction Online Database (1965-presente, ~738K reports).
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from hypokrates.canada.constants import CANADA_DB_FILENAME
from hypokrates.faers_bulk.models import AGE_GROUPS, StrataFilter
from hypokrates.store.base import BaseDuckDBStore

if TYPE_CHECKING:
    from pathlib import Path

logger = logging.getLogger(__name__)

_CREATE_TABLES_SQL = """
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


class CanadaVigilanceStore(BaseDuckDBStore):
    """Store DuckDB para dados do Canada Vigilance.

    Singleton thread-safe. Persiste em ``~/.cache/hypokrates/canada_vigilance.duckdb``.
    """

    _DB_FILENAME = CANADA_DB_FILENAME
    _CREATE_TABLES = _CREATE_TABLES_SQL

    def __init__(self, db_path: Path | None = None) -> None:
        super().__init__(db_path)
        self._loaded = self._check_loaded()

    @property
    def loaded(self) -> bool:
        """Se o store contém dados carregados."""
        return self._loaded

    def _check_loaded(self) -> bool:
        for table in ("canada_reports", "canada_drugs", "canada_reactions"):
            result = self._conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()
            if result is None or result[0] == 0:
                return False
        return True

    def load_from_csvs(self, csv_dir: str) -> int:
        """Carrega arquivos $-delimited do Canada Vigilance."""
        from hypokrates.canada.parser import load_files_to_store

        count = load_files_to_store(self, csv_dir)
        self._loaded = True
        return count

    def four_counts(
        self,
        drug: str,
        event: str,
        *,
        suspect_only: bool = False,
        strata: StrataFilter | None = None,
    ) -> tuple[int, int, int, int]:
        """Retorna (a, b, c, n) para calculo de PRR."""
        if strata is not None and not strata.is_empty:
            return self._four_counts_stratified(drug, event, suspect_only, strata)

        role = "suspect" if suspect_only else "all"
        with self._db_lock:
            row = self._conn.execute(_FOUR_COUNTS_SQL, [drug, event, role]).fetchone()

        if row is None:
            return 0, 0, 0, 0

        return int(row[0]), int(row[1]), int(row[2]), int(row[3])

    def _four_counts_stratified(
        self,
        drug: str,
        event: str,
        suspect_only: bool,
        strata: StrataFilter,
    ) -> tuple[int, int, int, int]:
        where_clauses: list[str] = []
        params: list[object] = [drug, event, "suspect" if suspect_only else "all"]

        if strata.sex is not None:
            # Canada uses "1"=Male, "2"=Female
            sex_code = {"M": "1", "F": "2"}.get(strata.sex.upper(), strata.sex)
            where_clauses.append(f"rpt.gender_code = ${len(params) + 1}")
            params.append(sex_code)

        if strata.age_group is not None and strata.age_group in AGE_GROUPS:
            lo, hi = AGE_GROUPS[strata.age_group]
            where_clauses.append(
                f"TRY_CAST(rpt.age AS INTEGER) >= ${len(params) + 1} "
                f"AND TRY_CAST(rpt.age AS INTEGER) < ${len(params) + 2}"
            )
            params.extend([lo, hi])

        strata_where = " AND ".join(where_clauses) if where_clauses else "1=1"

        sql = f"""
        WITH strata_reports AS (
            SELECT report_id FROM canada_reports rpt WHERE {strata_where}
        ),
        drug_reports AS (
            SELECT DISTINCT d.report_id
            FROM canada_drugs d
            JOIN canada_ingredients i ON d.drug_product_id = i.drug_product_id
            JOIN strata_reports sr ON d.report_id = sr.report_id
            WHERE UPPER(i.ingredient_name) = UPPER($1)
            AND ($3 = 'all' OR d.drug_role = 'Suspect')
        ),
        event_reports AS (
            SELECT DISTINCT r.report_id
            FROM canada_reactions r
            JOIN strata_reports sr ON r.report_id = sr.report_id
            WHERE UPPER(r.pt_name) = UPPER($2)
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
        total AS (SELECT COUNT(*) AS cnt FROM strata_reports)
        SELECT
            (SELECT cnt FROM a) AS a_count,
            (SELECT cnt FROM b) AS b_count,
            (SELECT cnt FROM c) AS c_count,
            (SELECT cnt FROM total) AS total_count
        """

        with self._db_lock:
            row = self._conn.execute(sql, params).fetchone()

        if row is None:
            return 0, 0, 0, 0

        return int(row[0]), int(row[1]), int(row[2]), int(row[3])

    def top_events(
        self,
        drug: str,
        *,
        suspect_only: bool = False,
        limit: int = 10,
        strata: StrataFilter | None = None,
    ) -> list[tuple[str, int]]:
        """Retorna top eventos adversos para uma droga."""
        role = "suspect" if suspect_only else "all"

        if strata is not None and not strata.is_empty:
            return self._top_events_stratified(drug, suspect_only, limit, strata)

        with self._db_lock:
            rows = self._conn.execute(_TOP_EVENTS_SQL, [drug, role, limit]).fetchall()

        return [(row[0], int(row[1])) for row in rows]

    def _top_events_stratified(
        self,
        drug: str,
        suspect_only: bool,
        limit: int,
        strata: StrataFilter,
    ) -> list[tuple[str, int]]:
        where_clauses: list[str] = []
        params: list[object] = [drug, "suspect" if suspect_only else "all", limit]

        if strata.sex is not None:
            # Canada uses "1"=Male, "2"=Female
            sex_code = {"M": "1", "F": "2"}.get(strata.sex.upper(), strata.sex)
            where_clauses.append(f"rpt.gender_code = ${len(params) + 1}")
            params.append(sex_code)

        if strata.age_group is not None and strata.age_group in AGE_GROUPS:
            lo, hi = AGE_GROUPS[strata.age_group]
            where_clauses.append(
                f"TRY_CAST(rpt.age AS INTEGER) >= ${len(params) + 1} "
                f"AND TRY_CAST(rpt.age AS INTEGER) < ${len(params) + 2}"
            )
            params.extend([lo, hi])

        strata_where = " AND ".join(where_clauses) if where_clauses else "1=1"

        sql = f"""
        WITH strata_reports AS (
            SELECT report_id FROM canada_reports rpt WHERE {strata_where}
        )
        SELECT r.pt_name, COUNT(DISTINCT r.report_id) AS cnt
        FROM canada_reactions r
        JOIN canada_drugs d ON r.report_id = d.report_id
        JOIN canada_ingredients i ON d.drug_product_id = i.drug_product_id
        JOIN strata_reports sr ON r.report_id = sr.report_id
        WHERE UPPER(i.ingredient_name) = UPPER($1)
        AND ($2 = 'all' OR d.drug_role = 'Suspect')
        AND r.pt_name != ''
        GROUP BY r.pt_name
        ORDER BY cnt DESC
        LIMIT $3
        """

        with self._db_lock:
            rows = self._conn.execute(sql, params).fetchall()

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
