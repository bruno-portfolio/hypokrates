"""DrugBank DuckDB store — indexa dados parseados para lookup rápido.

Armazena em DuckDB separado do cache HTTP para evitar lock contention.
Parse do XML acontece 1x; chamadas subsequentes usam o DuckDB persistido.
"""

from __future__ import annotations

import json
import logging
import threading
from typing import TYPE_CHECKING, Any, ClassVar

import duckdb

from hypokrates.drugbank.constants import DRUGBANK_DB_FILENAME
from hypokrates.drugbank.models import (
    DrugBankInfo,
    DrugEnzyme,
    DrugInteraction,
    DrugTarget,
)
from hypokrates.drugbank.parser import iterparse_drugbank

if TYPE_CHECKING:
    from pathlib import Path

logger = logging.getLogger(__name__)

_CREATE_TABLES = """
CREATE TABLE IF NOT EXISTS drugbank_drugs (
    drugbank_id VARCHAR PRIMARY KEY,
    name VARCHAR NOT NULL,
    description VARCHAR DEFAULT '',
    mechanism_of_action VARCHAR DEFAULT '',
    pharmacodynamics VARCHAR DEFAULT '',
    categories VARCHAR DEFAULT '[]',
    synonyms VARCHAR DEFAULT '[]'
);

CREATE TABLE IF NOT EXISTS drugbank_interactions (
    drug_id VARCHAR NOT NULL,
    partner_id VARCHAR NOT NULL,
    partner_name VARCHAR NOT NULL,
    description VARCHAR DEFAULT ''
);

CREATE TABLE IF NOT EXISTS drugbank_targets (
    drug_id VARCHAR NOT NULL,
    name VARCHAR NOT NULL,
    gene_name VARCHAR DEFAULT '',
    actions VARCHAR DEFAULT '[]',
    organism VARCHAR DEFAULT 'Humans'
);

CREATE TABLE IF NOT EXISTS drugbank_enzymes (
    drug_id VARCHAR NOT NULL,
    name VARCHAR NOT NULL,
    gene_name VARCHAR DEFAULT ''
);

CREATE TABLE IF NOT EXISTS drugbank_name_index (
    name_lower VARCHAR NOT NULL,
    drugbank_id VARCHAR NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_name_index_name
    ON drugbank_name_index (name_lower);
"""


class DrugBankStore:
    """Store DuckDB para dados do DrugBank.

    Singleton thread-safe. Persiste em ``~/.cache/hypokrates/drugbank.duckdb``.
    """

    _instance: ClassVar[DrugBankStore | None] = None
    _lock: ClassVar[threading.Lock] = threading.Lock()

    def __init__(self, db_path: Path | None = None) -> None:
        if db_path is None:
            from hypokrates.config import get_config

            db_path = get_config().cache_dir / DRUGBANK_DB_FILENAME
        db_path.parent.mkdir(parents=True, exist_ok=True)
        self._db_path = db_path
        self._conn = duckdb.connect(str(db_path))
        self._conn.execute(_CREATE_TABLES)
        self._loaded = self._check_loaded()

    @classmethod
    def get_instance(cls) -> DrugBankStore:
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
        result = self._conn.execute("SELECT COUNT(*) FROM drugbank_drugs").fetchone()
        return result is not None and result[0] > 0

    def load_from_xml(self, xml_path: str) -> int:
        """Carrega dados do DrugBank XML para o DuckDB.

        Args:
            xml_path: Caminho para o arquivo DrugBank XML.

        Returns:
            Número de drogas carregadas.
        """
        logger.info("Loading DrugBank XML: %s", xml_path)
        drugs = iterparse_drugbank(xml_path)

        if not drugs:
            logger.warning("No drugs found in DrugBank XML")
            return 0

        # Limpar tabelas antes de carregar
        self._conn.execute("DELETE FROM drugbank_name_index")
        self._conn.execute("DELETE FROM drugbank_enzymes")
        self._conn.execute("DELETE FROM drugbank_targets")
        self._conn.execute("DELETE FROM drugbank_interactions")
        self._conn.execute("DELETE FROM drugbank_drugs")

        self._batch_insert(drugs)

        self._loaded = True
        logger.info("DrugBank loaded: %d drugs", len(drugs))
        return len(drugs)

    def _batch_insert(self, drugs: list[dict[str, Any]]) -> None:
        """Insere todas as drogas em batch (executemany)."""
        drug_rows: list[list[object]] = []
        name_rows: list[list[str]] = []
        interaction_rows: list[list[str]] = []
        target_rows: list[list[str]] = []
        enzyme_rows: list[list[str]] = []

        for drug in drugs:
            drug_id = drug["drugbank_id"]
            name = drug["name"]

            drug_rows.append(
                [
                    drug_id,
                    name,
                    drug["description"],
                    drug["mechanism_of_action"],
                    drug["pharmacodynamics"],
                    json.dumps(drug["categories"]),
                    json.dumps(drug["synonyms"]),
                ]
            )

            name_rows.append([name.lower(), drug_id])
            for synonym in drug["synonyms"]:
                name_rows.append([synonym.lower(), drug_id])

            for interaction in drug["interactions"]:
                interaction_rows.append(
                    [
                        drug_id,
                        interaction["partner_id"],
                        interaction["partner_name"],
                        interaction["description"],
                    ]
                )

            for target in drug["targets"]:
                target_rows.append(
                    [
                        drug_id,
                        target["name"],
                        target["gene_name"],
                        json.dumps(target["actions"]),
                        target["organism"],
                    ]
                )

            for enzyme in drug["enzymes"]:
                enzyme_rows.append(
                    [
                        drug_id,
                        enzyme["name"],
                        enzyme["gene_name"],
                    ]
                )

        if drug_rows:
            self._conn.executemany(
                "INSERT INTO drugbank_drugs VALUES (?, ?, ?, ?, ?, ?, ?)",
                drug_rows,
            )
        if name_rows:
            self._conn.executemany(
                "INSERT INTO drugbank_name_index VALUES (?, ?)",
                name_rows,
            )
        if interaction_rows:
            self._conn.executemany(
                "INSERT INTO drugbank_interactions VALUES (?, ?, ?, ?)",
                interaction_rows,
            )
        if target_rows:
            self._conn.executemany(
                "INSERT INTO drugbank_targets VALUES (?, ?, ?, ?, ?)",
                target_rows,
            )
        if enzyme_rows:
            self._conn.executemany(
                "INSERT INTO drugbank_enzymes VALUES (?, ?, ?)",
                enzyme_rows,
            )

    def find_drug(self, name: str) -> DrugBankInfo | None:
        """Busca droga por nome ou sinônimo (case-insensitive).

        Returns:
            DrugBankInfo ou None se não encontrado.
        """
        # Lookup na name_index
        result = self._conn.execute(
            "SELECT drugbank_id FROM drugbank_name_index WHERE name_lower = ? LIMIT 1",
            [name.lower()],
        ).fetchone()

        if result is None:
            return None

        drug_id: str = result[0]
        return self.get_drug(drug_id)

    def get_drug(self, drug_id: str) -> DrugBankInfo | None:
        """Busca droga pelo DrugBank ID.

        Returns:
            DrugBankInfo ou None se não encontrado.
        """
        row = self._conn.execute(
            "SELECT * FROM drugbank_drugs WHERE drugbank_id = ?",
            [drug_id],
        ).fetchone()

        if row is None:
            return None

        targets = self._get_targets(drug_id)
        enzymes = self._get_enzymes(drug_id)
        interactions = self._get_interactions(drug_id)

        return DrugBankInfo(
            drugbank_id=row[0],
            name=row[1],
            description=row[2],
            mechanism_of_action=row[3],
            pharmacodynamics=row[4],
            categories=json.loads(row[5]),
            synonyms=json.loads(row[6]),
            targets=targets,
            enzymes=enzymes,
            interactions=interactions,
        )

    def find_interactions(self, name: str) -> list[DrugInteraction]:
        """Busca interações de uma droga por nome."""
        result = self._conn.execute(
            "SELECT drugbank_id FROM drugbank_name_index WHERE name_lower = ? LIMIT 1",
            [name.lower()],
        ).fetchone()

        if result is None:
            return []

        return self._get_interactions(result[0])

    def _get_targets(self, drug_id: str) -> list[DrugTarget]:
        """Busca targets de uma droga."""
        rows = self._conn.execute(
            "SELECT name, gene_name, actions, organism FROM drugbank_targets WHERE drug_id = ?",
            [drug_id],
        ).fetchall()

        return [
            DrugTarget(
                name=row[0],
                gene_name=row[1],
                actions=json.loads(row[2]),
                organism=row[3],
            )
            for row in rows
        ]

    def _get_enzymes(self, drug_id: str) -> list[DrugEnzyme]:
        """Busca enzimas de uma droga."""
        rows = self._conn.execute(
            "SELECT name, gene_name FROM drugbank_enzymes WHERE drug_id = ?",
            [drug_id],
        ).fetchall()

        return [DrugEnzyme(name=row[0], gene_name=row[1]) for row in rows]

    def _get_interactions(self, drug_id: str) -> list[DrugInteraction]:
        """Busca interações de uma droga."""
        rows = self._conn.execute(
            "SELECT partner_id, partner_name, description "
            "FROM drugbank_interactions WHERE drug_id = ?",
            [drug_id],
        ).fetchall()

        return [
            DrugInteraction(
                partner_id=row[0],
                partner_name=row[1],
                description=row[2],
            )
            for row in rows
        ]

    def close(self) -> None:
        """Fecha a conexão DuckDB."""
        if self._conn is not None:
            self._conn.close()
            self._conn = None  # type: ignore[assignment]
