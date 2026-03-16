"""API pública do módulo Canada Vigilance — async-first."""

from __future__ import annotations

import asyncio
import logging
from datetime import UTC, datetime

from hypokrates.canada.models import CanadaBulkStatus, CanadaSignalResult
from hypokrates.canada.store import CanadaVigilanceStore
from hypokrates.config import get_config
from hypokrates.exceptions import ConfigurationError
from hypokrates.models import MetaInfo

logger = logging.getLogger(__name__)

# Limiares simples para detecção de sinal (PRR)
_MIN_REPORTS = 3
_MIN_PRR = 2.0


async def _ensure_loaded(
    _store: CanadaVigilanceStore | None = None,
) -> CanadaVigilanceStore:
    """Garante que o store está carregado."""
    if _store is not None:
        return _store

    store = CanadaVigilanceStore.get_instance()
    if store.loaded:
        return store

    config = get_config()
    if config.canada_bulk_path is None:
        raise ConfigurationError(
            "canada_bulk_path",
            "Use configure(canada_bulk_path='/path/to/extracted/') first.",
        )

    csv_dir = str(config.canada_bulk_path)
    logger.info("Canada Vigilance store not loaded — loading: %s", csv_dir)
    await asyncio.to_thread(store.load_from_csvs, csv_dir)
    return store


async def canada_signal(
    drug: str,
    event: str,
    *,
    suspect_only: bool = False,
    _store: CanadaVigilanceStore | None = None,
) -> CanadaSignalResult:
    """Calcula PRR para drug-event no Canada Vigilance.

    Usa a mesma fórmula de PRR do FAERS: PRR = (a/a+b) / (c/c+d).

    Args:
        drug: Nome do ingrediente ativo.
        event: Termo MedDRA (PT) do evento adverso.
        suspect_only: Se True, conta apenas reports onde a droga é Suspect.
        _store: Store injetado (para testes).

    Returns:
        CanadaSignalResult com PRR e flag de sinal.
    """
    store = await _ensure_loaded(_store)
    a, b, c, n = await asyncio.to_thread(store.four_counts, drug, event, suspect_only=suspect_only)

    # PRR = (a/(a+b)) / (c/(c+d)) onde d = n - a - b - c
    d = n - a - b - c
    prr = 0.0
    if a > 0 and (a + b) > 0 and (c + d) > 0 and c > 0:
        prr = (a / (a + b)) / (c / (c + d))

    signal_detected = a >= _MIN_REPORTS and prr >= _MIN_PRR

    return CanadaSignalResult(
        drug=drug,
        event=event,
        drug_event_count=a,
        drug_total=a + b,
        event_total=a + c,
        total_reports=n,
        prr=round(prr, 2),
        signal_detected=signal_detected,
        meta=MetaInfo(
            source="Canada Vigilance",
            query={"drug": drug, "event": event, "suspect_only": suspect_only},
            total_results=a,
            retrieved_at=datetime.now(UTC),
            disclaimer="Canada Vigilance: voluntary adverse reaction reports (1965-present). "
            "PRR is a measure of disproportionality, not absolute risk. "
            "Cross-country validation with FAERS increases confidence.",
        ),
    )


async def canada_top_events(
    drug: str,
    *,
    limit: int = 10,
    suspect_only: bool = False,
    _store: CanadaVigilanceStore | None = None,
) -> list[tuple[str, int]]:
    """Retorna top eventos adversos para uma droga no Canada Vigilance.

    Args:
        drug: Nome do ingrediente ativo.
        limit: Máximo de eventos.
        suspect_only: Se True, conta apenas Suspect.
        _store: Store injetado (para testes).

    Returns:
        Lista de (event_term, count) ordenada por count DESC.
    """
    store = await _ensure_loaded(_store)
    return await asyncio.to_thread(store.top_events, drug, suspect_only=suspect_only, limit=limit)


async def canada_bulk_status(
    *,
    _store: CanadaVigilanceStore | None = None,
) -> CanadaBulkStatus:
    """Retorna status do Canada Vigilance store.

    Args:
        _store: Store injetado (para testes).

    Returns:
        CanadaBulkStatus com contagens e data range.
    """
    store = await _ensure_loaded(_store)

    total_reports = await asyncio.to_thread(store.count_reports)
    total_drugs = await asyncio.to_thread(store.count_drugs)
    total_reactions = await asyncio.to_thread(store.count_reactions)
    date_range = await asyncio.to_thread(store.date_range)

    return CanadaBulkStatus(
        loaded=True,
        total_reports=total_reports,
        total_drugs=total_drugs,
        total_reactions=total_reactions,
        date_range=date_range,
        meta=MetaInfo(
            source="Canada Vigilance",
            query={"action": "status"},
            total_results=total_reports,
            retrieved_at=datetime.now(UTC),
        ),
    )
