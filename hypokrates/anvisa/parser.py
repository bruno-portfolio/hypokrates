"""Parser de CSV da ANVISA (medicamentos registrados)."""

from __future__ import annotations

import csv
import logging
from pathlib import Path
from typing import Any

from hypokrates.anvisa.constants import (
    ACCENT_MAP,
    COL_ATC,
    COL_CATEGORIA,
    COL_COMPLEMENTO,
    COL_EMPRESA,
    COL_NOME,
    COL_REFERENCIA,
    COL_REGISTRO,
    COL_SUBSTANCIAS,
    COL_TARJA,
    CSV_DELIMITER,
    CSV_ENCODING,
    REQUIRED_COLUMNS,
)
from hypokrates.exceptions import ParseError

logger = logging.getLogger(__name__)

_ACCENT_TABLE = str.maketrans(ACCENT_MAP)


def normalize_text(text: str) -> str:
    """Uppercase + strip acentos para indexação de busca."""
    return text.upper().translate(_ACCENT_TABLE).strip()


def split_substancias(raw: str) -> list[str]:
    """Separa substancias ativas (delimitador ',' ou '+')."""
    if not raw:
        return []
    parts: list[str] = []
    for chunk in raw.replace("+", ",").split(","):
        cleaned = chunk.strip()
        if cleaned:
            parts.append(cleaned)
    return parts


def split_apresentacoes(complemento: str) -> list[str]:
    """Separa apresentações do campo COMPLEMENTO."""
    if not complemento:
        return []
    parts: list[str] = []
    for chunk in complemento.split(","):
        cleaned = chunk.strip()
        if cleaned:
            parts.append(cleaned)
    return parts


def parse_medicamentos_csv(csv_path: str | Path) -> list[dict[str, Any]]:
    """Parseia CSV de medicamentos da ANVISA.

    Args:
        csv_path: Caminho para o arquivo CSV.

    Returns:
        Lista de dicts normalizados prontos para inserção no DuckDB.

    Raises:
        ParseError: Se colunas obrigatórias estiverem faltando.
    """
    path = Path(csv_path)
    logger.info("Parsing ANVISA CSV: %s", path)

    rows: list[dict[str, Any]] = []
    with path.open(encoding=CSV_ENCODING, errors="replace") as f:
        reader = csv.DictReader(f, delimiter=CSV_DELIMITER, quotechar='"')
        if reader.fieldnames is None:
            msg = f"CSV vazio ou sem header: {path}"
            raise ParseError(msg)

        fields = set(reader.fieldnames)
        missing = REQUIRED_COLUMNS - fields
        if missing:
            msg = f"Colunas obrigatorias faltando: {missing}"
            raise ParseError(msg)

        for i, row in enumerate(reader):
            registro = (row.get(COL_REGISTRO) or "").strip()
            nome = (row.get(COL_NOME) or "").strip()
            if not registro or not nome:
                continue

            substancias_raw = (row.get(COL_SUBSTANCIAS) or "").strip()
            rows.append(
                {
                    "registro": registro,
                    "nome_produto": nome,
                    "substancias": substancias_raw,
                    "categoria": (row.get(COL_CATEGORIA) or "").strip(),
                    "referencia": (row.get(COL_REFERENCIA) or "").strip(),
                    "atc": (row.get(COL_ATC) or "").strip(),
                    "tarja": (row.get(COL_TARJA) or "").strip(),
                    "complemento": (row.get(COL_COMPLEMENTO) or "").strip(),
                    "empresa": (row.get(COL_EMPRESA) or "").strip(),
                    "substancias_norm": normalize_text(substancias_raw),
                }
            )

            if (i + 1) % 10_000 == 0:
                logger.info("  parsed %d rows...", i + 1)

    logger.info("ANVISA CSV parsed: %d medicamentos", len(rows))
    return rows
