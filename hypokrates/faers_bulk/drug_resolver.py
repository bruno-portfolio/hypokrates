"""Resolve nome de droga para o formato normalizado do bulk store.

Match direto em drug_name_norm (UPPER input). Se não encontrar,
tenta normalize_drug() via RxNorm para obter o nome genérico.
Cache in-memory para evitar queries repetidas.
"""

from __future__ import annotations

import asyncio
import logging
import threading
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from hypokrates.faers_bulk.store import FAERSBulkStore

logger = logging.getLogger(__name__)

# Cache in-memory: input → resolved name (ou None se não encontrado)
_resolve_cache: dict[str, str | None] = {}
_cache_lock = threading.Lock()


async def resolve_bulk_drug(
    drug: str,
    *,
    store: FAERSBulkStore | None = None,
) -> str | None:
    """Resolve nome de droga para o drug_name_norm do bulk store.

    1. Match exato em UPPER(input) contra drug_name_norm
    2. Se não encontrar, tenta RxNorm (normalize_drug) → UPPER → re-check
    3. Se ainda não: return None (caller faz fallback para API)

    Args:
        drug: Nome da droga (qualquer case).
        store: FAERSBulkStore opcional (default: singleton).

    Returns:
        Nome normalizado se encontrado, None caso contrário.
    """
    drug_upper = drug.strip().upper()
    if not drug_upper:
        return None

    # Check cache
    with _cache_lock:
        if drug_upper in _resolve_cache:
            return _resolve_cache[drug_upper]

    if store is None:
        from hypokrates.faers_bulk.store import FAERSBulkStore

        store = FAERSBulkStore.get_instance()

    # Tier 1: match direto
    found = await asyncio.to_thread(_check_drug_exists, store, drug_upper)
    if found:
        with _cache_lock:
            _resolve_cache[drug_upper] = drug_upper
        return drug_upper

    # Tier 2: RxNorm resolve para generic name
    try:
        from hypokrates.vocab import api as vocab_api

        normalized = await vocab_api.normalize_drug(drug)
        if normalized and normalized.generic_name:
            generic_upper = normalized.generic_name.strip().upper()
            if generic_upper != drug_upper:
                found = await asyncio.to_thread(_check_drug_exists, store, generic_upper)
                if found:
                    with _cache_lock:
                        _resolve_cache[drug_upper] = generic_upper
                    logger.info(
                        "Bulk drug resolved via RxNorm: %s → %s",
                        drug,
                        generic_upper,
                    )
                    return generic_upper
    except Exception:
        logger.debug("RxNorm resolution failed for %s, skipping", drug)

    # Not found
    with _cache_lock:
        _resolve_cache[drug_upper] = None
    return None


def _check_drug_exists(store: FAERSBulkStore, drug_name_norm: str) -> bool:
    """Verifica se existe ao menos 1 row com drug_name_norm no store."""
    with store._db_lock:
        result = store._conn.execute(
            "SELECT 1 FROM faers_drug WHERE drug_name_norm = ? LIMIT 1",
            [drug_name_norm],
        ).fetchone()
    return result is not None


def clear_cache() -> None:
    """Limpa cache de resolução (usado em testes)."""
    with _cache_lock:
        _resolve_cache.clear()
