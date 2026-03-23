"""OnSIDES DuckDB store — indexa dados de bulas de 4 países via NLP.

Armazena em DuckDB separado do cache HTTP para evitar lock contention.
Parse dos CSVs acontece 1x; chamadas subsequentes usam o DuckDB persistido.

Fonte: OnSIDES — 7.1M drug-ADE pairs extraídos por PubMedBERT de 51,460 bulas
de US/EU/UK/JP. Download manual (313MB ZIP).
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from hypokrates.onsides.constants import (
    DEFAULT_MIN_CONFIDENCE,
    ONSIDES_DB_FILENAME,
)
from hypokrates.store.base import BaseDuckDBStore

if TYPE_CHECKING:
    from pathlib import Path

    from hypokrates.onsides.models import OnSIDESEvent

logger = logging.getLogger(__name__)

_CREATE_TABLES_SQL = """
CREATE TABLE IF NOT EXISTS product_label (
    label_id INTEGER PRIMARY KEY,
    source VARCHAR NOT NULL,
    source_product_name VARCHAR DEFAULT '',
    source_product_id VARCHAR DEFAULT '',
    source_label_url VARCHAR DEFAULT ''
);

CREATE TABLE IF NOT EXISTS product_adverse_effect (
    product_label_id INTEGER NOT NULL,
    effect_id INTEGER DEFAULT 0,
    label_section VARCHAR DEFAULT '',
    effect_meddra_id INTEGER NOT NULL,
    match_method VARCHAR DEFAULT '',
    pred0 DOUBLE DEFAULT 0.0,
    pred1 DOUBLE DEFAULT 0.0
);

CREATE TABLE IF NOT EXISTS product_to_rxnorm (
    label_id INTEGER NOT NULL,
    rxnorm_product_id VARCHAR NOT NULL
);

CREATE TABLE IF NOT EXISTS vocab_rxnorm_product (
    rxnorm_id VARCHAR PRIMARY KEY,
    rxnorm_name VARCHAR DEFAULT '',
    rxnorm_term_type VARCHAR DEFAULT ''
);

CREATE TABLE IF NOT EXISTS vocab_rxnorm_ingredient_to_product (
    product_id VARCHAR NOT NULL,
    ingredient_id VARCHAR NOT NULL
);

CREATE TABLE IF NOT EXISTS vocab_rxnorm_ingredient (
    rxnorm_id VARCHAR PRIMARY KEY,
    rxnorm_name VARCHAR DEFAULT '',
    rxnorm_term_type VARCHAR DEFAULT ''
);

CREATE TABLE IF NOT EXISTS vocab_meddra_adverse_effect (
    meddra_id INTEGER PRIMARY KEY,
    meddra_name VARCHAR DEFAULT '',
    meddra_term_type VARCHAR DEFAULT ''
);

CREATE INDEX IF NOT EXISTS idx_ingredient_name
    ON vocab_rxnorm_ingredient (LOWER(rxnorm_name));

CREATE INDEX IF NOT EXISTS idx_adverse_effect_label
    ON product_adverse_effect (product_label_id);

CREATE INDEX IF NOT EXISTS idx_ingredient_to_product
    ON vocab_rxnorm_ingredient_to_product (ingredient_id);

CREATE INDEX IF NOT EXISTS idx_product_to_rxnorm
    ON product_to_rxnorm (rxnorm_product_id);
"""

_EVENTS_QUERY = """
SELECT
    m.meddra_id,
    m.meddra_name,
    a.label_section,
    MAX(a.pred1) AS max_confidence,
    LIST(DISTINCT l.source ORDER BY l.source) AS sources
FROM vocab_rxnorm_ingredient i
JOIN vocab_rxnorm_ingredient_to_product ip ON i.rxnorm_id = ip.ingredient_id
JOIN product_to_rxnorm pr ON ip.product_id = pr.rxnorm_product_id
JOIN product_label l ON pr.label_id = l.label_id
JOIN product_adverse_effect a ON l.label_id = a.product_label_id
JOIN vocab_meddra_adverse_effect m ON a.effect_meddra_id = m.meddra_id
WHERE LOWER(i.rxnorm_name) = LOWER($1)
  AND a.pred1 >= $2
GROUP BY m.meddra_id, m.meddra_name, a.label_section
ORDER BY max_confidence DESC
"""

_CHECK_EVENT_QUERY = """
SELECT
    m.meddra_id,
    m.meddra_name,
    a.label_section,
    MAX(a.pred1) AS max_confidence,
    LIST(DISTINCT l.source ORDER BY l.source) AS sources
FROM vocab_rxnorm_ingredient i
JOIN vocab_rxnorm_ingredient_to_product ip ON i.rxnorm_id = ip.ingredient_id
JOIN product_to_rxnorm pr ON ip.product_id = pr.rxnorm_product_id
JOIN product_label l ON pr.label_id = l.label_id
JOIN product_adverse_effect a ON l.label_id = a.product_label_id
JOIN vocab_meddra_adverse_effect m ON a.effect_meddra_id = m.meddra_id
WHERE LOWER(i.rxnorm_name) = LOWER($1)
  AND LOWER(m.meddra_name) = LOWER($2)
GROUP BY m.meddra_id, m.meddra_name, a.label_section
ORDER BY max_confidence DESC
LIMIT 1
"""


class OnSIDESStore(BaseDuckDBStore):
    """Store DuckDB para dados do OnSIDES.

    Singleton thread-safe. Persiste em ``~/.cache/hypokrates/onsides.duckdb``.
    Todas as queries são protegidas por ``_db_lock`` para segurança com
    ``asyncio.to_thread()`` (chamadas concorrentes de threads diferentes).
    """

    _DB_FILENAME = ONSIDES_DB_FILENAME
    _CREATE_TABLES = _CREATE_TABLES_SQL

    def __init__(self, db_path: Path | None = None) -> None:
        super().__init__(db_path)
        self._loaded = self._check_loaded()

    @property
    def loaded(self) -> bool:
        """Se o store contém dados carregados."""
        return self._loaded

    def _check_loaded(self) -> bool:
        result = self._conn.execute("SELECT COUNT(*) FROM product_label").fetchone()
        return result is not None and result[0] > 0

    def load_from_csvs(self, csv_dir: str) -> int:
        """Carrega CSVs do OnSIDES para o DuckDB."""
        from hypokrates.onsides.parser import load_csvs_to_store

        count = load_csvs_to_store(self, csv_dir)
        self._loaded = True
        return count

    def query_events(
        self, drug: str, *, min_confidence: float = DEFAULT_MIN_CONFIDENCE
    ) -> list[OnSIDESEvent]:
        """Busca eventos adversos para uma droga."""
        from hypokrates.onsides.models import OnSIDESEvent

        with self._db_lock:
            rows = self._conn.execute(_EVENTS_QUERY, [drug, min_confidence]).fetchall()

        return [
            OnSIDESEvent(
                meddra_id=row[0],
                meddra_name=row[1],
                label_section=row[2],
                confidence=round(row[3], 4),
                sources=row[4],
                num_sources=len(row[4]),
            )
            for row in rows
        ]

    def check_event(self, drug: str, event: str) -> OnSIDESEvent | None:
        """Verifica se um evento especifico esta nas bulas da droga."""
        from hypokrates.onsides.models import OnSIDESEvent

        with self._db_lock:
            row = self._conn.execute(_CHECK_EVENT_QUERY, [drug, event]).fetchone()

        if row is None:
            return None

        return OnSIDESEvent(
            meddra_id=row[0],
            meddra_name=row[1],
            label_section=row[2],
            confidence=round(row[3], 4),
            sources=row[4],
            num_sources=len(row[4]),
        )

    def read_csv_in_lock(self, table: str, csv_path: str) -> int:
        """Lê CSV diretamente no DuckDB via read_csv (mais eficiente que executemany)."""
        with self._db_lock:
            self._conn.execute(
                f"INSERT INTO {table} SELECT * FROM read_csv('{csv_path}', "
                f"header=true, all_varchar=true)"
            )
            result = self._conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()
            return result[0] if result else 0
