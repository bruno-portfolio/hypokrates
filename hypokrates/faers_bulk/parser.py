"""Parser streaming para FAERS quarterly ASCII files (ZIP).

Formato: arquivos $-delimited (DEMO, DRUG, REAC) dentro de ZIP.
Usa header row para mapear colunas (resiliente a mudanças de formato entre anos).
"""

from __future__ import annotations

import csv
import io
import logging
import zipfile
from typing import TYPE_CHECKING

from hypokrates.faers_bulk.constants import DELIMITER, ENCODING
from hypokrates.faers_bulk.normalizer import normalize_drug_name

if TYPE_CHECKING:
    from collections.abc import Iterator
    from pathlib import Path

logger = logging.getLogger(__name__)


def parse_quarter_zip(
    zip_path: str | Path,
) -> tuple[list[dict[str, str]], list[dict[str, str]], list[dict[str, str]]]:
    """Parseia um ZIP de quarter FAERS ASCII.

    Extrai arquivos DEMO, DRUG e REAC do ZIP.
    Cada row vira um dict com chaves em lowercase.

    Args:
        zip_path: Caminho para o ZIP (e.g., ``faers_ascii_2024Q3.zip``).

    Returns:
        Tupla (demo_rows, drug_rows, reac_rows).

    Raises:
        FileNotFoundError: Se o ZIP não existe.
        ValueError: Se arquivos obrigatórios não encontrados no ZIP.
    """
    zip_path_str = str(zip_path)
    logger.info("Parsing FAERS quarter ZIP: %s", zip_path_str)

    with zipfile.ZipFile(zip_path_str, "r") as zf:
        demo_name = _find_file_in_zip(zf, "DEMO")
        drug_name = _find_file_in_zip(zf, "DRUG")
        reac_name = _find_file_in_zip(zf, "REAC")

        demo_rows = list(_parse_file_from_zip(zf, demo_name))
        logger.info("DEMO parsed: %d rows", len(demo_rows))

        drug_rows = _parse_drug_file(zf, drug_name)
        logger.info("DRUG parsed: %d rows", len(drug_rows))

        reac_rows = _parse_reac_file(zf, reac_name)
        logger.info("REAC parsed: %d rows", len(reac_rows))

    return demo_rows, drug_rows, reac_rows


def _find_file_in_zip(zf: zipfile.ZipFile, prefix: str) -> str:
    """Encontra arquivo com prefixo dentro do ZIP (case-insensitive).

    FDA é inconsistente com capitalização e estrutura de diretórios.
    Busca arquivos .txt cujo basename começa com o prefixo.

    Args:
        zf: ZipFile aberto.
        prefix: Prefixo do arquivo (DEMO, DRUG, REAC).

    Returns:
        Nome do arquivo dentro do ZIP.

    Raises:
        ValueError: Se nenhum arquivo matching encontrado.
    """
    prefix_upper = prefix.upper()
    for name in zf.namelist():
        # Pega apenas o basename (pode ter subdiretórios)
        basename = name.rsplit("/", maxsplit=1)[-1]
        if basename.upper().startswith(prefix_upper) and basename.upper().endswith(".TXT"):
            return name

    msg = f"Arquivo {prefix}*.txt não encontrado no ZIP"
    raise ValueError(msg)


def _parse_file_from_zip(
    zf: zipfile.ZipFile,
    filename: str,
) -> Iterator[dict[str, str]]:
    """Parseia um arquivo $-delimited de dentro do ZIP.

    Lê header row para mapear índices → nomes de coluna.
    Colunas faltantes em rows individuais viram string vazia.

    Args:
        zf: ZipFile aberto.
        filename: Nome do arquivo dentro do ZIP.

    Yields:
        Dicts com chaves em lowercase.
    """
    with zf.open(filename) as raw:
        text_stream = io.TextIOWrapper(raw, encoding=ENCODING, errors="replace")
        reader = csv.reader(text_stream, delimiter=DELIMITER)

        # Header row
        header_row = next(reader, None)
        if header_row is None:
            return

        # Normalizar headers: lowercase, strip
        headers = [h.strip().lower() for h in header_row]

        for row in reader:
            if not row or (len(row) == 1 and not row[0].strip()):
                continue
            record: dict[str, str] = {}
            for i, col_name in enumerate(headers):
                if i < len(row):
                    record[col_name] = row[i].strip()
                else:
                    record[col_name] = ""
            yield record


def _parse_drug_file(
    zf: zipfile.ZipFile,
    filename: str,
) -> list[dict[str, str]]:
    """Parseia DRUG file, adicionando drug_name_norm."""
    rows: list[dict[str, str]] = []
    for record in _parse_file_from_zip(zf, filename):
        prod_ai = record.get("prod_ai", "")
        drugname = record.get("drugname", "")
        record["drug_name_norm"] = normalize_drug_name(prod_ai, drugname)
        rows.append(record)
    return rows


def _parse_reac_file(
    zf: zipfile.ZipFile,
    filename: str,
) -> list[dict[str, str]]:
    """Parseia REAC file, adicionando pt_upper."""
    rows: list[dict[str, str]] = []
    for record in _parse_file_from_zip(zf, filename):
        pt = record.get("pt", "")
        record["pt_upper"] = pt.strip().upper()
        rows.append(record)
    return rows
