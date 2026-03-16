"""OnSIDES DuckDB store — indexa dados de bulas de 4 países via NLP.

Armazena em DuckDB separado do cache HTTP para evitar lock contention.
Parse dos CSVs acontece 1x; chamadas subsequentes usam o DuckDB persistido.

Fonte: OnSIDES — 7.1M drug-ADE pairs extraídos por PubMedBERT de 51,460 bulas
de US/EU/UK/JP. Download manual (313MB ZIP).
"""

from __future__ import annotations

import logging
import threading
from typing import TYPE_CHECKING, ClassVar

import duckdb

from hypokrates.onsides.constants import (
    DEFAULT_MIN_CONFIDENCE,
    ONSIDES_DB_FILENAME,
)

if TYPE_CHECKING:
    from pathlib import Path

    from hypokrates.onsides.models import OnSIDESEvent

logger = logging.getLogger(__name__)

_CREATE_TABLES = """
CREATE TABLE IF NOT EXISTS product_label (
    label_id INTEGER PRIMARY KEY,
    source VARCHAR NOT NULL,
    source_product_name VARCHAR DEFAULT ''
);

CREATE TABLE IF NOT EXISTS product_adverse_effect (
    product_label_id INTEGER NOT NULL,
    effect_meddra_id INTEGER NOT NULL,
    label_section VARCHAR DEFAULT '',
    pred1 DOUBLE DEFAULT 0.0
);

CREATE TABLE IF NOT EXISTS product_to_rxnorm (
    label_id INTEGER NOT NULL,
    rxnorm_product_id INTEGER NOT NULL
);

CREATE TABLE IF NOT EXISTS vocab_rxnorm_product (
    rxnorm_id INTEGER PRIMARY KEY,
    rxnorm_name VARCHAR DEFAULT '',
    term_type VARCHAR DEFAULT ''
);

CREATE TABLE IF NOT EXISTS vocab_rxnorm_ingredient_to_product (
    ingredient_id INTEGER NOT NULL,
    product_id INTEGER NOT NULL
);

CREATE TABLE IF NOT EXISTS vocab_rxnorm_ingredient (
    rxnorm_id INTEGER PRIMARY KEY,
    rxnorm_name VARCHAR DEFAULT ''
);

CREATE TABLE IF NOT EXISTS vocab_meddra_adverse_effect (
    meddra_id INTEGER PRIMARY KEY,
    meddra_name VARCHAR DEFAULT '',
    term_type VARCHAR DEFAULT ''
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

# Query principal: dado um ingredient name, retorna todos os AEs com country sources
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


class OnSIDESStore:
    """Store DuckDB para dados do OnSIDES.

    Singleton thread-safe. Persiste em ``~/.cache/hypokrates/onsides.duckdb``.
    Todas as queries são protegidas por ``_db_lock`` para segurança com
    ``asyncio.to_thread()`` (chamadas concorrentes de threads diferentes).
    """

    _instance: ClassVar[OnSIDESStore | None] = None
    _lock: ClassVar[threading.Lock] = threading.Lock()

    def __init__(self, db_path: Path | None = None) -> None:
        if db_path is None:
            from hypokrates.config import get_config

            db_path = get_config().cache_dir / ONSIDES_DB_FILENAME
        db_path.parent.mkdir(parents=True, exist_ok=True)
        self._db_path = db_path
        self._conn = duckdb.connect(str(db_path))
        self._db_lock = threading.Lock()
        self._conn.execute(_CREATE_TABLES)
        self._loaded = self._check_loaded()

    @classmethod
    def get_instance(cls) -> OnSIDESStore:
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
        result = self._conn.execute("SELECT COUNT(*) FROM product_label").fetchone()
        return result is not None and result[0] > 0

    def load_from_csvs(self, csv_dir: str) -> int:
        """Carrega CSVs do OnSIDES para o DuckDB.

        Args:
            csv_dir: Diretório contendo os CSVs extraídos do ZIP.

        Returns:
            Número de labels carregados.
        """
        from hypokrates.onsides.parser import load_csvs_to_store

        count = load_csvs_to_store(self, csv_dir)
        self._loaded = True
        return count

    def query_events(
        self, drug: str, *, min_confidence: float = DEFAULT_MIN_CONFIDENCE
    ) -> list[OnSIDESEvent]:
        """Busca eventos adversos para uma droga.

        Args:
            drug: Nome genérico do ingrediente (RxNorm).
            min_confidence: Confiança mínima (pred1) para filtrar.

        Returns:
            Lista de OnSIDESEvent ordenada por confiança descendente.
        """
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
        """Verifica se um evento específico está nas bulas da droga.

        Args:
            drug: Nome genérico do ingrediente.
            event: Termo MedDRA do evento adverso.

        Returns:
            OnSIDESEvent ou None se não encontrado.
        """
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

    def execute_in_lock(self, sql: str, params: list[object] | None = None) -> None:
        """Executa SQL dentro do lock (para uso pelo parser)."""
        with self._db_lock:
            if params:
                self._conn.execute(sql, params)
            else:
                self._conn.execute(sql)

    def executemany_in_lock(self, sql: str, rows: list[list[object]]) -> None:
        """Executa SQL com múltiplas linhas dentro do lock."""
        with self._db_lock:
            self._conn.executemany(sql, rows)

    def read_csv_in_lock(self, table: str, csv_path: str) -> int:
        """Lê CSV diretamente no DuckDB via read_csv (mais eficiente que executemany)."""
        with self._db_lock:
            self._conn.execute(
                f"INSERT INTO {table} SELECT * FROM read_csv('{csv_path}', "
                f"header=true, auto_detect=true)"
            )
            result = self._conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()
            return result[0] if result else 0

    def close(self) -> None:
        """Fecha a conexão DuckDB."""
        with self._db_lock:
            if self._conn is not None:
                self._conn.close()
                self._conn = None  # type: ignore[assignment]
