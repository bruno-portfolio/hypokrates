"""API publica do modulo ANVISA — async-first."""

from __future__ import annotations

import asyncio
import logging
from typing import TYPE_CHECKING

from hypokrates.anvisa.constants import (
    ANVISA_CSV_FILENAME,
    ANVISA_MEDICAMENTOS_URL,
    ANVISA_REFRESH_DAYS,
)
from hypokrates.anvisa.store import AnvisaStore
from hypokrates.download.base import download_file, needs_refresh

if TYPE_CHECKING:
    from hypokrates.anvisa.models import AnvisaNomeMapping, AnvisaSearchResult

logger = logging.getLogger(__name__)


async def _ensure_loaded(
    *,
    _store: AnvisaStore | None = None,
) -> AnvisaStore:
    """Garante que o store esta carregado.

    Auto-download do CSV se necessario.
    """
    store = _store if _store is not None else AnvisaStore.get_instance()
    if store.loaded:
        loaded_at = await asyncio.to_thread(store.get_loaded_at)
        if not needs_refresh(loaded_at, max_age_days=ANVISA_REFRESH_DAYS):
            return store

    # Verificar se ha CSV configurado manualmente
    from hypokrates.config import get_config

    config = get_config()
    csv_path = config.anvisa_csv_path

    if csv_path is None:
        # Auto-download
        logger.info("ANVISA store not loaded — downloading CSV")
        csv_path = config.cache_dir / "anvisa" / ANVISA_CSV_FILENAME
        await download_file(
            ANVISA_MEDICAMENTOS_URL,
            csv_path,
            label="ANVISA Medicamentos",
            timeout=120.0,
            verify=False,
        )

    logger.info("Loading ANVISA CSV: %s", csv_path)
    await asyncio.to_thread(store.load_from_csv, csv_path)
    return store


async def buscar_medicamento(
    nome: str,
    *,
    limit: int = 20,
    _store: AnvisaStore | None = None,
) -> AnvisaSearchResult:
    """Busca medicamento por nome comercial ou principio ativo.

    Suporta busca parcial e accent-insensitive.
    Exemplo: "metf" → encontra METFORMINA.

    Args:
        nome: Nome ou parte do nome da droga (PT ou EN).
        limit: Maximo de resultados.
        _store: Store injetado (para testes).

    Returns:
        AnvisaSearchResult com medicamentos encontrados.
    """
    store = await _ensure_loaded(_store=_store)
    return await asyncio.to_thread(store.search, nome, limit=limit)


async def buscar_por_substancia(
    substancia: str,
    *,
    categoria: str | None = None,
    limit: int = 50,
    _store: AnvisaStore | None = None,
) -> AnvisaSearchResult:
    """Busca todos os produtos registrados contendo uma substancia ativa.

    Args:
        substancia: Nome do principio ativo (PT ou EN).
        categoria: Filtro opcional: "Genérico", "Similar", "Referência".
        limit: Maximo de resultados.
        _store: Store injetado (para testes).

    Returns:
        AnvisaSearchResult com medicamentos encontrados.
    """
    store = await _ensure_loaded(_store=_store)
    return await asyncio.to_thread(
        store.search_by_substancia,
        substancia,
        categoria=categoria,
        limit=limit,
    )


async def listar_apresentacoes(
    nome: str,
    *,
    _store: AnvisaStore | None = None,
) -> AnvisaSearchResult:
    """Lista todas as apresentacoes/dosagens de um medicamento.

    Args:
        nome: Nome do medicamento ou principio ativo.
        _store: Store injetado (para testes).

    Returns:
        AnvisaSearchResult com medicamentos e suas apresentacoes.
    """
    store = await _ensure_loaded(_store=_store)
    return await asyncio.to_thread(store.search, nome, limit=50)


async def mapear_nome(
    nome: str,
    *,
    _store: AnvisaStore | None = None,
) -> AnvisaNomeMapping | None:
    """Mapeia nome brasileiro <-> nome internacional.

    Primeiro verifica mapeamento estatico, depois tenta RxNorm.

    Args:
        nome: Nome da droga em portugues ou ingles.
        _store: Store injetado (para testes).

    Returns:
        AnvisaNomeMapping ou None se nao encontrado.
    """
    store = await _ensure_loaded(_store=_store)
    result = await asyncio.to_thread(store.map_nome, nome)
    if result is not None:
        return result

    # Fallback: tentar via RxNorm
    try:
        from hypokrates.vocab import api as vocab_api

        norm = await vocab_api.normalize_drug(nome)
        if norm and norm.generic_name:
            from hypokrates.anvisa.models import AnvisaNomeMapping as Mapping

            return Mapping(
                nome_pt=nome.upper(),
                nome_en=norm.generic_name.upper(),
                source="rxnorm",
            )
    except Exception:
        logger.debug("RxNorm fallback failed for '%s'", nome)

    return None
