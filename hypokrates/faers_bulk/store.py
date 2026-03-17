"""FAERS Bulk DuckDB store — deduplicação por CASEID.

Armazena em DuckDB separado do cache HTTP (mesmo padrão DrugBank).
Parse dos ZIPs acontece 1x por quarter; chamadas subsequentes usam DuckDB persistido.
"""

from __future__ import annotations

import logging
import threading
from datetime import UTC, datetime
from typing import TYPE_CHECKING, ClassVar

import duckdb

from hypokrates.faers_bulk.constants import (
    BATCH_SIZE,
    FAERS_BULK_DB_FILENAME,
    RoleCodFilter,
)
from hypokrates.faers_bulk.models import (
    AGE_GROUPS,
    MIN_STRATUM_DRUG_EVENT,
    MIN_STRATUM_DRUG_TOTAL,
    BulkCountResult,
    BulkStoreStatus,
    QuarterInfo,
    StrataFilter,
)
from hypokrates.faers_bulk.parser import parse_quarter_zip

if TYPE_CHECKING:
    from pathlib import Path

logger = logging.getLogger(__name__)

_CREATE_TABLES = """
CREATE TABLE IF NOT EXISTS faers_demo (
    primaryid VARCHAR NOT NULL,
    caseid VARCHAR NOT NULL,
    caseversion INTEGER NOT NULL,
    event_dt VARCHAR DEFAULT '',
    age VARCHAR DEFAULT '',
    sex VARCHAR DEFAULT '',
    reporter_country VARCHAR DEFAULT '',
    quarter_key VARCHAR NOT NULL
);

CREATE TABLE IF NOT EXISTS faers_drug (
    primaryid VARCHAR NOT NULL,
    drug_seq VARCHAR DEFAULT '0',
    role_cod VARCHAR DEFAULT '',
    drugname VARCHAR DEFAULT '',
    prod_ai VARCHAR DEFAULT '',
    drug_name_norm VARCHAR DEFAULT '',
    route VARCHAR DEFAULT ''
);

CREATE TABLE IF NOT EXISTS faers_reac (
    primaryid VARCHAR NOT NULL,
    pt VARCHAR NOT NULL,
    pt_upper VARCHAR NOT NULL
);

CREATE TABLE IF NOT EXISTS faers_dedup (
    caseid VARCHAR PRIMARY KEY,
    primaryid VARCHAR NOT NULL,
    caseversion INTEGER NOT NULL
);

CREATE TABLE IF NOT EXISTS faers_quarters (
    quarter_key VARCHAR PRIMARY KEY,
    year INTEGER NOT NULL,
    quarter INTEGER NOT NULL,
    loaded_at TIMESTAMP NOT NULL,
    demo_count INTEGER DEFAULT 0,
    drug_count INTEGER DEFAULT 0,
    reac_count INTEGER DEFAULT 0
);

CREATE INDEX IF NOT EXISTS idx_drug_primaryid ON faers_drug (primaryid);
CREATE INDEX IF NOT EXISTS idx_drug_norm ON faers_drug (drug_name_norm);
CREATE INDEX IF NOT EXISTS idx_drug_role ON faers_drug (role_cod);
CREATE INDEX IF NOT EXISTS idx_reac_primaryid ON faers_reac (primaryid);
CREATE INDEX IF NOT EXISTS idx_reac_pt ON faers_reac (pt_upper);
CREATE INDEX IF NOT EXISTS idx_demo_primaryid ON faers_demo (primaryid);
CREATE INDEX IF NOT EXISTS idx_demo_caseid ON faers_demo (caseid);
"""

_FOUR_COUNTS_SQL = """
WITH deduped AS (
    SELECT primaryid FROM faers_dedup
),
drug_pids AS (
    SELECT DISTINCT d.primaryid
    FROM faers_drug d
    INNER JOIN deduped dd ON d.primaryid = dd.primaryid
    WHERE d.drug_name_norm = $drug
    AND (
        $role = 'all'
        OR ($role = 'suspect' AND d.role_cod IN ('PS', 'SS'))
        OR ($role = 'ps_only' AND d.role_cod = 'PS')
    )
),
event_pids AS (
    SELECT DISTINCT r.primaryid
    FROM faers_reac r
    INNER JOIN deduped dd ON r.primaryid = dd.primaryid
    WHERE r.pt_upper = ANY($events)
)
SELECT
    (SELECT COUNT(*) FROM drug_pids dp
     INNER JOIN event_pids ep ON dp.primaryid = ep.primaryid) AS a,
    (SELECT COUNT(*) FROM drug_pids) AS ab,
    (SELECT COUNT(*) FROM event_pids) AS ac,
    (SELECT COUNT(*) FROM deduped) AS n
"""


_TOP_EVENTS_SQL = """
WITH deduped AS (
    SELECT primaryid FROM faers_dedup
),
drug_pids AS (
    SELECT DISTINCT d.primaryid
    FROM faers_drug d
    INNER JOIN deduped dd ON d.primaryid = dd.primaryid
    WHERE d.drug_name_norm = $drug
    AND (
        $role = 'all'
        OR ($role = 'suspect' AND d.role_cod IN ('PS', 'SS'))
        OR ($role = 'ps_only' AND d.role_cod = 'PS')
    )
)
SELECT r.pt_upper AS event, COUNT(DISTINCT dp.primaryid) AS cnt
FROM drug_pids dp
INNER JOIN faers_reac r ON dp.primaryid = r.primaryid
GROUP BY r.pt_upper
ORDER BY cnt DESC
LIMIT $limit
"""

_DRUG_TOTAL_SQL = """
WITH deduped AS (
    SELECT primaryid FROM faers_dedup
)
SELECT COUNT(DISTINCT d.primaryid)
FROM faers_drug d
INNER JOIN deduped dd ON d.primaryid = dd.primaryid
WHERE d.drug_name_norm = $drug
AND (
    $role = 'all'
    OR ($role = 'suspect' AND d.role_cod IN ('PS', 'SS'))
    OR ($role = 'ps_only' AND d.role_cod = 'PS')
)
"""


class FAERSBulkStore:
    """Store DuckDB para FAERS quarterly ASCII files.

    Singleton thread-safe. Persiste em ``~/.cache/hypokrates/faers_bulk.duckdb``.
    Todas as queries são protegidas por ``_db_lock`` para segurança com
    ``asyncio.to_thread()`` (chamadas concorrentes de threads diferentes).
    """

    _instance: ClassVar[FAERSBulkStore | None] = None
    _lock: ClassVar[threading.Lock] = threading.Lock()

    def __init__(self, db_path: Path | None = None) -> None:
        if db_path is None:
            from hypokrates.config import get_config

            db_path = get_config().cache_dir / FAERS_BULK_DB_FILENAME
        db_path.parent.mkdir(parents=True, exist_ok=True)
        self._db_path = db_path
        self._conn = duckdb.connect(str(db_path))
        self._db_lock = threading.Lock()
        self._conn.execute(_CREATE_TABLES)

    @classmethod
    def get_instance(cls) -> FAERSBulkStore:
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

    def is_loaded(self) -> bool:
        """Se o store contém ao menos um quarter carregado."""
        with self._db_lock:
            result = self._conn.execute("SELECT COUNT(*) FROM faers_quarters").fetchone()
            return result is not None and result[0] > 0

    def load_quarter(self, zip_path: str | Path, *, force: bool = False) -> int:
        """Carrega um quarter FAERS ASCII ZIP para o DuckDB (idempotente)."""
        quarter_key = _extract_quarter_key(str(zip_path))

        with self._db_lock:
            if not force:
                existing = self._conn.execute(
                    "SELECT 1 FROM faers_quarters WHERE quarter_key = $1",
                    [quarter_key],
                ).fetchone()
                if existing is not None:
                    logger.info("Quarter %s already loaded, skipping", quarter_key)
                    return 0

        logger.info("Loading quarter %s from %s", quarter_key, zip_path)
        demo_rows, drug_rows, reac_rows = parse_quarter_zip(zip_path)

        with self._db_lock:
            if force:
                self._delete_quarter_unlocked(quarter_key)

            self._batch_insert_demo(demo_rows, quarter_key)
            self._batch_insert_drug(drug_rows)
            self._batch_insert_reac(reac_rows)

            self._conn.execute(
                "INSERT OR REPLACE INTO faers_quarters VALUES ($1, $2, $3, $4, $5, $6, $7)",
                [
                    quarter_key,
                    _year_from_key(quarter_key),
                    _quarter_from_key(quarter_key),
                    datetime.now(UTC),
                    len(demo_rows),
                    len(drug_rows),
                    len(reac_rows),
                ],
            )

            dedup_count = self._rebuild_dedup_unlocked()

        logger.info(
            "Quarter %s loaded: %d demo, %d drug, %d reac, %d deduped cases",
            quarter_key,
            len(demo_rows),
            len(drug_rows),
            len(reac_rows),
            dedup_count,
        )
        return len(demo_rows)

    def rebuild_dedup(self) -> int:
        """Rebuild do índice de deduplicação (mantém maior caseversion por caseid)."""
        with self._db_lock:
            return self._rebuild_dedup_unlocked()

    def _rebuild_dedup_unlocked(self) -> int:
        self._conn.execute("DELETE FROM faers_dedup")
        self._conn.execute(
            """
            INSERT INTO faers_dedup (caseid, primaryid, caseversion)
            SELECT caseid, primaryid, caseversion
            FROM (
                SELECT caseid, primaryid, caseversion,
                       ROW_NUMBER() OVER (
                           PARTITION BY caseid ORDER BY caseversion DESC
                       ) AS rn
                FROM faers_demo
            ) ranked
            WHERE rn = 1
            """
        )
        result = self._conn.execute("SELECT COUNT(*) FROM faers_dedup").fetchone()
        count: int = result[0] if result else 0
        return count

    def four_counts(
        self,
        drug: str,
        event: str | list[str],
        *,
        role_filter: RoleCodFilter = RoleCodFilter.SUSPECT,
        strata: StrataFilter | None = None,
    ) -> BulkCountResult:
        """Calcula 4-count deduplicado para um par droga-evento."""
        drug_upper = drug.strip().upper()
        if isinstance(event, list):
            events_list = [e.strip().upper() for e in event]
        else:
            events_list = [event.strip().upper()]
        role_value = role_filter.value

        if strata is not None and not strata.is_empty:
            return self._four_counts_stratified(drug_upper, events_list, role_value, strata)

        with self._db_lock:
            result = self._conn.execute(
                _FOUR_COUNTS_SQL,
                {"drug": drug_upper, "events": events_list, "role": role_value},
            ).fetchone()

        if result is None:
            return BulkCountResult(drug_event=0, drug_total=0, event_total=0, n_total=0)

        return BulkCountResult(
            drug_event=result[0],
            drug_total=result[1],
            event_total=result[2],
            n_total=result[3],
        )

    def _four_counts_stratified(
        self,
        drug: str,
        events: list[str],
        role: str,
        strata: StrataFilter,
    ) -> BulkCountResult:
        where_clauses: list[str] = []
        params: dict[str, object] = {"drug": drug, "events": events, "role": role}

        if strata.sex is not None:
            where_clauses.append("dm.sex = $sex")
            params["sex"] = strata.sex.upper()

        if strata.age_group is not None and strata.age_group in AGE_GROUPS:
            lo, hi = AGE_GROUPS[strata.age_group]
            where_clauses.append(
                "TRY_CAST(dm.age AS INTEGER) >= $age_lo AND TRY_CAST(dm.age AS INTEGER) < $age_hi"
            )
            params["age_lo"] = lo
            params["age_hi"] = hi

        if strata.reporter_country is not None:
            where_clauses.append("dm.reporter_country = $country")
            params["country"] = strata.reporter_country.upper()

        strata_where = " AND ".join(where_clauses) if where_clauses else "1=1"

        sql = f"""
        WITH strata_pids AS (
            SELECT dd.primaryid
            FROM faers_dedup dd
            JOIN faers_demo dm ON dd.primaryid = dm.primaryid
            WHERE {strata_where}
        ),
        drug_pids AS (
            SELECT DISTINCT d.primaryid
            FROM faers_drug d
            INNER JOIN strata_pids sp ON d.primaryid = sp.primaryid
            WHERE d.drug_name_norm = $drug
            AND (
                $role = 'all'
                OR ($role = 'suspect' AND d.role_cod IN ('PS', 'SS'))
                OR ($role = 'ps_only' AND d.role_cod = 'PS')
            )
        ),
        event_pids AS (
            SELECT DISTINCT r.primaryid
            FROM faers_reac r
            INNER JOIN strata_pids sp ON r.primaryid = sp.primaryid
            WHERE r.pt_upper = ANY($events)
        )
        SELECT
            (SELECT COUNT(*) FROM drug_pids dp
             INNER JOIN event_pids ep ON dp.primaryid = ep.primaryid) AS a,
            (SELECT COUNT(*) FROM drug_pids) AS ab,
            (SELECT COUNT(*) FROM event_pids) AS ac,
            (SELECT COUNT(*) FROM strata_pids) AS n
        """

        with self._db_lock:
            result = self._conn.execute(sql, params).fetchone()

        if result is None:
            return BulkCountResult(drug_event=0, drug_total=0, event_total=0, n_total=0)

        a, ab, ac, n = int(result[0]), int(result[1]), int(result[2]), int(result[3])

        if a < MIN_STRATUM_DRUG_EVENT or ab < MIN_STRATUM_DRUG_TOTAL:
            return BulkCountResult(
                drug_event=a,
                drug_total=ab,
                event_total=ac,
                n_total=n,
                insufficient_data=True,
                insufficient_reason=(
                    f"Stratum too small: {a} drug+event reports, {ab} drug total"
                ),
            )

        return BulkCountResult(drug_event=a, drug_total=ab, event_total=ac, n_total=n)

    def top_events(
        self,
        drug: str,
        *,
        role_filter: RoleCodFilter = RoleCodFilter.SUSPECT,
        limit: int = 60,
        strata: StrataFilter | None = None,
    ) -> list[tuple[str, int]]:
        """Retorna os eventos mais reportados para uma droga (deduplicado)."""
        drug_upper = drug.strip().upper()
        role_value = role_filter.value

        if strata is not None and not strata.is_empty:
            return self._top_events_stratified(drug_upper, role_value, limit, strata)

        with self._db_lock:
            rows = self._conn.execute(
                _TOP_EVENTS_SQL,
                {"drug": drug_upper, "role": role_value, "limit": limit},
            ).fetchall()

        return [(row[0], row[1]) for row in rows]

    def _top_events_stratified(
        self,
        drug: str,
        role: str,
        limit: int,
        strata: StrataFilter,
    ) -> list[tuple[str, int]]:
        where_clauses: list[str] = []
        params: dict[str, object] = {"drug": drug, "role": role, "limit": limit}

        if strata.sex is not None:
            where_clauses.append("dm.sex = $sex")
            params["sex"] = strata.sex.upper()

        if strata.age_group is not None and strata.age_group in AGE_GROUPS:
            lo, hi = AGE_GROUPS[strata.age_group]
            where_clauses.append(
                "TRY_CAST(dm.age AS INTEGER) >= $age_lo AND TRY_CAST(dm.age AS INTEGER) < $age_hi"
            )
            params["age_lo"] = lo
            params["age_hi"] = hi

        if strata.reporter_country is not None:
            where_clauses.append("dm.reporter_country = $country")
            params["country"] = strata.reporter_country.upper()

        strata_where = " AND ".join(where_clauses) if where_clauses else "1=1"

        sql = f"""
        WITH strata_pids AS (
            SELECT dd.primaryid
            FROM faers_dedup dd
            JOIN faers_demo dm ON dd.primaryid = dm.primaryid
            WHERE {strata_where}
        ),
        drug_pids AS (
            SELECT DISTINCT d.primaryid
            FROM faers_drug d
            INNER JOIN strata_pids sp ON d.primaryid = sp.primaryid
            WHERE d.drug_name_norm = $drug
            AND (
                $role = 'all'
                OR ($role = 'suspect' AND d.role_cod IN ('PS', 'SS'))
                OR ($role = 'ps_only' AND d.role_cod = 'PS')
            )
        )
        SELECT r.pt_upper AS event, COUNT(DISTINCT dp.primaryid) AS cnt
        FROM drug_pids dp
        INNER JOIN faers_reac r ON dp.primaryid = r.primaryid
        GROUP BY r.pt_upper
        ORDER BY cnt DESC
        LIMIT $limit
        """

        with self._db_lock:
            rows = self._conn.execute(sql, params).fetchall()

        return [(row[0], row[1]) for row in rows]

    def drug_total(
        self,
        drug: str,
        *,
        role_filter: RoleCodFilter = RoleCodFilter.SUSPECT,
    ) -> int:
        """Total de cases deduplicados que mencionam a droga com o role dado."""
        drug_upper = drug.strip().upper()
        role_value = role_filter.value

        with self._db_lock:
            result = self._conn.execute(
                _DRUG_TOTAL_SQL,
                {"drug": drug_upper, "role": role_value},
            ).fetchone()

        return result[0] if result else 0

    def count_total(self) -> int:
        """Total de cases deduplicados (N)."""
        with self._db_lock:
            result = self._conn.execute("SELECT COUNT(*) FROM faers_dedup").fetchone()
            return result[0] if result else 0

    def get_status(self) -> BulkStoreStatus:
        """Status completo do store."""
        quarters = self.get_loaded_quarters()

        with self._db_lock:
            demo_count = self._conn.execute("SELECT COUNT(*) FROM faers_demo").fetchone()
            dedup_count = self._conn.execute("SELECT COUNT(*) FROM faers_dedup").fetchone()
            drug_count = self._conn.execute("SELECT COUNT(*) FROM faers_drug").fetchone()
            reac_count = self._conn.execute("SELECT COUNT(*) FROM faers_reac").fetchone()

        total_reports = demo_count[0] if demo_count else 0
        deduped_cases = dedup_count[0] if dedup_count else 0
        total_drug = drug_count[0] if drug_count else 0
        total_reac = reac_count[0] if reac_count else 0

        oldest = min((q.quarter_key for q in quarters), default=None)
        newest = max((q.quarter_key for q in quarters), default=None)

        return BulkStoreStatus(
            total_reports=total_reports,
            deduped_cases=deduped_cases,
            total_drug_records=total_drug,
            total_reac_records=total_reac,
            quarters_loaded=quarters,
            oldest_quarter=oldest,
            newest_quarter=newest,
        )

    def get_loaded_quarters(self) -> list[QuarterInfo]:
        """Lista quarters carregados."""
        with self._db_lock:
            rows = self._conn.execute(
                "SELECT quarter_key, year, quarter, loaded_at, demo_count, drug_count, reac_count "
                "FROM faers_quarters ORDER BY quarter_key"
            ).fetchall()

        return [
            QuarterInfo(
                quarter_key=row[0],
                year=row[1],
                quarter=row[2],
                loaded_at=row[3],
                demo_count=row[4],
                drug_count=row[5],
                reac_count=row[6],
            )
            for row in rows
        ]

    def _delete_quarter_unlocked(self, quarter_key: str) -> None:
        self._conn.execute(
            "DELETE FROM faers_drug WHERE primaryid IN "
            "(SELECT primaryid FROM faers_demo WHERE quarter_key = $1)",
            [quarter_key],
        )
        self._conn.execute(
            "DELETE FROM faers_reac WHERE primaryid IN "
            "(SELECT primaryid FROM faers_demo WHERE quarter_key = $1)",
            [quarter_key],
        )
        self._conn.execute(
            "DELETE FROM faers_demo WHERE quarter_key = $1",
            [quarter_key],
        )
        self._conn.execute(
            "DELETE FROM faers_quarters WHERE quarter_key = $1",
            [quarter_key],
        )

    def _batch_insert_demo(self, rows: list[dict[str, str]], quarter_key: str) -> None:
        batch: list[list[str | int]] = []
        for row in rows:
            caseversion_str = row.get("caseversion", "0")
            try:
                caseversion = int(caseversion_str)
            except (ValueError, TypeError):
                caseversion = 0

            batch.append(
                [
                    row.get("primaryid", ""),
                    row.get("caseid", ""),
                    caseversion,
                    row.get("event_dt", ""),
                    row.get("age", ""),
                    row.get("sex", ""),
                    row.get("reporter_country", row.get("occr_country", "")),
                    quarter_key,
                ]
            )

            if len(batch) >= BATCH_SIZE:
                self._conn.executemany(
                    "INSERT INTO faers_demo VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                    batch,
                )
                batch.clear()

        if batch:
            self._conn.executemany(
                "INSERT INTO faers_demo VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                batch,
            )

    def _batch_insert_drug(self, rows: list[dict[str, str]]) -> None:
        batch: list[list[str]] = []
        for row in rows:
            batch.append(
                [
                    row.get("primaryid", ""),
                    row.get("drug_seq", "0"),
                    row.get("role_cod", ""),
                    row.get("drugname", ""),
                    row.get("prod_ai", ""),
                    row.get("drug_name_norm", ""),
                    row.get("route", ""),
                ]
            )

            if len(batch) >= BATCH_SIZE:
                self._conn.executemany(
                    "INSERT INTO faers_drug VALUES (?, ?, ?, ?, ?, ?, ?)",
                    batch,
                )
                batch.clear()

        if batch:
            self._conn.executemany(
                "INSERT INTO faers_drug VALUES (?, ?, ?, ?, ?, ?, ?)",
                batch,
            )

    def _batch_insert_reac(self, rows: list[dict[str, str]]) -> None:
        batch: list[list[str]] = []
        for row in rows:
            batch.append(
                [
                    row.get("primaryid", ""),
                    row.get("pt", ""),
                    row.get("pt_upper", ""),
                ]
            )

            if len(batch) >= BATCH_SIZE:
                self._conn.executemany(
                    "INSERT INTO faers_reac VALUES (?, ?, ?)",
                    batch,
                )
                batch.clear()

        if batch:
            self._conn.executemany(
                "INSERT INTO faers_reac VALUES (?, ?, ?)",
                batch,
            )

    def close(self) -> None:
        """Fecha a conexão DuckDB."""
        with self._db_lock:
            if self._conn is not None:
                self._conn.close()
                self._conn = None  # type: ignore[assignment]


def _extract_quarter_key(zip_path: str) -> str:
    """Extrai quarter_key (e.g., '2024Q3') do nome do ZIP; fallback para stem."""
    import re

    match = re.search(r"(\d{4})[qQ](\d)", zip_path)
    if match:
        return f"{match.group(1)}Q{match.group(2)}"

    from pathlib import Path

    return Path(zip_path).stem


def _year_from_key(quarter_key: str) -> int:
    return int(quarter_key[:4])


def _quarter_from_key(quarter_key: str) -> int:
    return int(quarter_key[-1])
