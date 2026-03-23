"""API pública do módulo OnSIDES — async-first."""

from __future__ import annotations

import asyncio
import logging
from datetime import UTC, datetime
from typing import TYPE_CHECKING

from hypokrates.config import get_config
from hypokrates.models import MetaInfo
from hypokrates.onsides.constants import DEFAULT_MIN_CONFIDENCE
from hypokrates.onsides.store import OnSIDESStore

if TYPE_CHECKING:
    from hypokrates.onsides.models import OnSIDESEvent, OnSIDESResult

logger = logging.getLogger(__name__)


async def _ensure_loaded(
    _store: OnSIDESStore | None = None,
) -> OnSIDESStore:
    """Garante que o store está carregado, com auto-download se necessário."""
    if _store is not None:
        return _store

    store = OnSIDESStore.get_instance()
    if store.loaded:
        return store

    config = get_config()

    # 1. Manual config override
    if config.onsides_path is not None:
        csv_dir = str(config.onsides_path)
        logger.info("OnSIDES store not loaded — loading CSVs: %s", csv_dir)
        await asyncio.to_thread(store.load_from_csvs, csv_dir)
        return store

    # 2. Auto-download
    from hypokrates.onsides.downloader import download_onsides

    logger.info("OnSIDES store not loaded — downloading data")
    csv_dir_path = await download_onsides()
    logger.info("Loading OnSIDES data from %s", csv_dir_path)
    await asyncio.to_thread(store.load_from_csvs, str(csv_dir_path))
    return store


async def onsides_events(
    drug: str,
    *,
    min_confidence: float = DEFAULT_MIN_CONFIDENCE,
    _store: OnSIDESStore | None = None,
) -> OnSIDESResult:
    """Busca eventos adversos de bulas internacionais via OnSIDES (NLP).

    OnSIDES contém 7.1M drug-ADE pairs extraídos por PubMedBERT de
    51,460 bulas de 4 países (US, EU, UK, JP).

    Args:
        drug: Nome genérico do ingrediente (e.g., "propofol").
        min_confidence: Confiança mínima para filtrar (0-1, default 0.5).
        _store: Store injetado (para testes).

    Returns:
        OnSIDESResult com eventos e metadata.
    """
    from hypokrates.onsides.models import OnSIDESResult

    store = await _ensure_loaded(_store)
    events = await asyncio.to_thread(store.query_events, drug, min_confidence=min_confidence)

    return OnSIDESResult(
        drug_name=drug,
        events=events,
        total_events=len(events),
        meta=MetaInfo(
            source="OnSIDES",
            query={"drug": drug, "min_confidence": min_confidence},
            total_results=len(events),
            retrieved_at=datetime.now(UTC),
            disclaimer="OnSIDES: NLP-extracted drug-ADE pairs from labels of "
            "4 countries (US/EU/UK/JP). Confidence scores are from PubMedBERT "
            "(F1=0.935). Not a substitute for manual label review.",
        ),
    )


async def onsides_check_event(
    drug: str,
    event: str,
    *,
    _store: OnSIDESStore | None = None,
) -> OnSIDESEvent | None:
    """Verifica se um evento específico está nas bulas internacionais da droga.

    Args:
        drug: Nome genérico do ingrediente.
        event: Termo MedDRA do evento adverso.
        _store: Store injetado (para testes).

    Returns:
        OnSIDESEvent se encontrado, None caso contrário.
    """
    store = await _ensure_loaded(_store)
    return await asyncio.to_thread(store.check_event, drug, event)
