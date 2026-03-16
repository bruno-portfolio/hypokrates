"""API pública do FAERS Bulk — async-first.

Expõe funcionalidades do bulk store para uso direto e integração
com signal() via dual-mode.
"""

from __future__ import annotations

import asyncio
import logging
from datetime import UTC, datetime

from hypokrates.faers_bulk.constants import RoleCodFilter
from hypokrates.faers_bulk.drug_resolver import resolve_bulk_drug
from hypokrates.faers_bulk.models import BulkStoreStatus  # noqa: TC001 — used at runtime
from hypokrates.faers_bulk.store import FAERSBulkStore
from hypokrates.models import MetaInfo
from hypokrates.stats.constants import (
    MIN_MEASURES_FOR_SIGNAL,
    MIN_REPORT_COUNT,
    SIGNAL_DISCLAIMER,
)
from hypokrates.stats.measures import (
    build_table,
    compute_ebgm,
    compute_ic,
    compute_prr,
    compute_ror,
)
from hypokrates.stats.models import SignalResult

logger = logging.getLogger(__name__)


async def is_bulk_available() -> bool:
    """Verifica se o FAERS Bulk store está carregado com dados."""
    try:
        store = FAERSBulkStore.get_instance()
        return await asyncio.to_thread(store.is_loaded)
    except Exception:
        return False


async def bulk_store_status() -> BulkStoreStatus:
    """Retorna status completo do FAERS Bulk store."""
    store = FAERSBulkStore.get_instance()
    return await asyncio.to_thread(store.get_status)


async def bulk_top_events(
    drug: str,
    *,
    role_filter: RoleCodFilter = RoleCodFilter.SUSPECT,
    limit: int = 60,
) -> list[tuple[str, int]]:
    """Retorna top eventos adversos de uma droga via bulk store (deduplicado).

    Args:
        drug: Nome genérico do medicamento.
        role_filter: Filtro de role (PS_ONLY, SUSPECT, ALL).
        limit: Máximo de eventos.

    Returns:
        Lista de (event_term, count) ordenada por count DESC.
    """
    store = FAERSBulkStore.get_instance()
    resolved = await resolve_bulk_drug(drug, store=store)
    drug_name = resolved if resolved is not None else drug.strip().upper()
    return await asyncio.to_thread(
        store.top_events, drug_name, role_filter=role_filter, limit=limit
    )


async def bulk_drug_total(
    drug: str,
    *,
    role_filter: RoleCodFilter = RoleCodFilter.SUSPECT,
) -> int:
    """Total de cases deduplicados que mencionam a droga.

    Args:
        drug: Nome genérico do medicamento.
        role_filter: Filtro de role.

    Returns:
        Contagem de cases.
    """
    store = FAERSBulkStore.get_instance()
    resolved = await resolve_bulk_drug(drug, store=store)
    drug_name = resolved if resolved is not None else drug.strip().upper()
    return await asyncio.to_thread(store.drug_total, drug_name, role_filter=role_filter)


async def bulk_signal(
    drug: str,
    event: str,
    *,
    role_filter: RoleCodFilter = RoleCodFilter.SUSPECT,
) -> SignalResult:
    """Calcula sinal de desproporcionalidade usando FAERS Bulk (deduplicado).

    Args:
        drug: Nome genérico do medicamento.
        event: Preferred term MedDRA do evento.
        role_filter: Filtro de role (PS_ONLY, SUSPECT, ALL).

    Returns:
        SignalResult com PRR, ROR, IC — mesmo modelo do API path.
    """
    store = FAERSBulkStore.get_instance()

    # Resolve drug name no store
    resolved = await resolve_bulk_drug(drug, store=store)
    drug_name = resolved if resolved is not None else drug.strip().upper()

    # Expandir sinônimos MedDRA para o evento
    from hypokrates.vocab.meddra import expand_event_terms

    event_terms = expand_event_terms(event)

    # Query bulk store (thread para não bloquear event loop)
    counts = await asyncio.to_thread(
        store.four_counts, drug_name, event_terms, role_filter=role_filter
    )

    # Construir sinal com mesma lógica do API path
    table = build_table(counts.drug_event, counts.drug_total, counts.event_total, counts.n_total)

    prr = compute_prr(table)
    ror = compute_ror(table)
    ic = compute_ic(table)
    ebgm = compute_ebgm(table)

    significant_count = sum([prr.significant, ror.significant, ic.significant])
    signal_detected = (
        counts.drug_event >= MIN_REPORT_COUNT and significant_count >= MIN_MEASURES_FOR_SIGNAL
    )

    disclaimer = (
        "This data is from FAERS quarterly ASCII files, deduplicated by CASEID. "
        "Signal does not imply causation. "
        f"{SIGNAL_DISCLAIMER}"
    )

    return SignalResult(
        drug=drug,
        event=event,
        table=table,
        prr=prr,
        ror=ror,
        ic=ic,
        ebgm=ebgm,
        signal_detected=signal_detected,
        meta=MetaInfo(
            source="FAERS/bulk (deduplicated)",
            query={
                "drug": drug,
                "event": event,
                "role_filter": role_filter.value,
            },
            total_results=counts.drug_event,
            retrieved_at=datetime.now(UTC),
            disclaimer=disclaimer,
        ),
    )
