"""API pública de detecção de sinais — async-first."""

from __future__ import annotations

import asyncio
import logging
import statistics as _statistics
from datetime import UTC, datetime
from typing import Any

from hypokrates.faers.api import resolve_drug_field
from hypokrates.faers.client import FAERSClient
from hypokrates.faers.constants import (
    COUNT_FIELDS,
    DRUG_CHARACTERIZATION_FIELD,
    DRUG_CHARACTERIZATION_SUSPECT,
    SEARCH_FIELDS,
)
from hypokrates.models import MetaInfo
from hypokrates.stats.constants import (
    MIN_MEASURES_FOR_SIGNAL,
    MIN_REPORT_COUNT,
    SIGNAL_DISCLAIMER,
    SPIKE_THRESHOLD_SIGMA,
)
from hypokrates.stats.measures import build_table, compute_ic, compute_prr, compute_ror
from hypokrates.stats.models import QuarterlyCount, SignalResult, TimelineResult
from hypokrates.vocab.meddra import expand_event_terms

logger = logging.getLogger(__name__)


def _build_reaction_query(event: str, reaction_field: str) -> str:
    """Constrói query de reação para FAERS, expandindo termos MedDRA.

    Se o evento é um canonical MedDRA (e.g., "QT PROLONGATION"), expande para
    todos os aliases (e.g., "ELECTROCARDIOGRAM QT PROLONGED", "LONG QT SYNDROME").
    """
    terms = expand_event_terms(event)
    if len(terms) == 1:
        return f'{reaction_field}:"{terms[0]}"'
    parts = [f'{reaction_field}:"{t}"' for t in terms]
    return "(" + "+".join(parts) + ")"


async def signal(
    drug: str,
    event: str,
    *,
    suspect_only: bool = False,
    primary_suspect_only: bool = False,
    use_bulk: bool | None = None,
    use_cache: bool = True,
    _client: FAERSClient | None = None,
    _drug_search: str | None = None,
    _drug_total: int | None = None,
    _n_total: int | None = None,
) -> SignalResult:
    """Calcula sinal de desproporcionalidade para um par droga-evento.

    Busca contagens no FAERS e calcula PRR, ROR e IC.

    Dual-mode: usa FAERS Bulk (deduplicado por CASEID) quando disponível,
    com fallback transparente para API OpenFDA.

    Nota: N (total geral do FAERS) é um snapshot do momento da query.
    O FAERS atualiza trimestralmente — o N muda entre updates.
    Cálculos usam N do momento da query, não N histórico fixo.
    Com TTL de 24h, queries entre updates do FAERS podem ter N
    levemente diferentes (cached vs fresh), mas a diferença é
    marginal (< 0.1% do total).

    Args:
        drug: Nome genérico do medicamento (e.g., "propofol").
        event: Termo do evento adverso MedDRA (e.g., "DEATH").
        suspect_only: Se True, conta apenas reports onde a droga é suspect.
        primary_suspect_only: Se True, conta apenas Primary Suspect (bulk only).
        use_bulk: None=auto-detect, True=forçar bulk, False=forçar API.
        use_cache: Se deve usar cache.

    Returns:
        SignalResult com PRR, ROR, IC e heurística signal_detected.
    """
    # --- Bulk path ---
    should_use_bulk = await _should_use_bulk(use_bulk)

    if should_use_bulk:
        from hypokrates.faers_bulk import api as bulk_api
        from hypokrates.faers_bulk.constants import RoleCodFilter

        if primary_suspect_only:
            role_filter = RoleCodFilter.PS_ONLY
        elif suspect_only:
            role_filter = RoleCodFilter.SUSPECT
        else:
            role_filter = RoleCodFilter.ALL

        return await bulk_api.bulk_signal(drug, event, role_filter=role_filter)

    # --- API path ---
    if primary_suspect_only:
        logger.warning(
            "primary_suspect_only requires bulk data; falling back to suspect_only "
            "(OpenFDA API does not distinguish PS from SS)"
        )
        suspect_only = True

    reaction_field = SEARCH_FIELDS["reaction"]
    reaction_query = _build_reaction_query(event, reaction_field)

    own_client = _client is None
    client = _client if _client is not None else FAERSClient()
    try:
        drug_search = (
            _drug_search
            if _drug_search is not None
            else await resolve_drug_field(drug, client=client, use_cache=use_cache)
        )

        char_filter = (
            f" AND {DRUG_CHARACTERIZATION_FIELD}:{DRUG_CHARACTERIZATION_SUSPECT}"
            if suspect_only
            else ""
        )
        search_drug_event = f"{drug_search}{char_filter} AND {reaction_query}"
        search_drug = f"{drug_search}{char_filter}"
        search_event = reaction_query

        if _drug_total is not None and _n_total is not None:
            # Scan path: apenas valores únicos por evento (paralelo)
            drug_event_count, event_total = await asyncio.gather(
                client.fetch_total(search_drug_event, use_cache=use_cache),
                client.fetch_total(search_event, use_cache=use_cache),
            )
            drug_total = _drug_total
            n_total = _n_total
        else:
            # Standalone path: todos em paralelo
            drug_event_count, drug_total, event_total, n_total = await asyncio.gather(
                client.fetch_total(search_drug_event, use_cache=use_cache),
                client.fetch_total(search_drug, use_cache=use_cache),
                client.fetch_total(search_event, use_cache=use_cache),
                client.fetch_total("", use_cache=use_cache),
            )
    finally:
        if own_client:
            await client.close()

    table = build_table(drug_event_count, drug_total, event_total, n_total)

    prr = compute_prr(table)
    ror = compute_ror(table)
    ic = compute_ic(table)

    significant_count = sum([prr.significant, ror.significant, ic.significant])
    signal_detected = (
        drug_event_count >= MIN_REPORT_COUNT and significant_count >= MIN_MEASURES_FOR_SIGNAL
    )

    disclaimer = (
        "This data is from voluntary reports and may contain errors. "
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
        signal_detected=signal_detected,
        meta=MetaInfo(
            source="OpenFDA/FAERS",
            query={"drug": drug, "event": event},
            total_results=drug_event_count,
            retrieved_at=datetime.now(UTC),
            disclaimer=disclaimer,
        ),
    )


async def _should_use_bulk(use_bulk: bool | None) -> bool:
    """Determina se deve usar bulk path."""
    if use_bulk is False:
        return False
    if use_bulk is True:
        return True
    # Auto-detect
    from hypokrates.faers_bulk.api import is_bulk_available

    return await is_bulk_available()


async def signal_timeline(
    drug: str,
    event: str,
    *,
    suspect_only: bool = False,
    use_bulk: bool | None = None,
    use_cache: bool = True,
) -> TimelineResult:
    """Série temporal trimestral de reports FAERS para um par droga-evento.

    Dual-mode: usa FAERS Bulk (deduplicado por CASEID) quando disponível,
    com fallback para API OpenFDA.

    Usa OpenFDA count=receivedate para obter contagens diárias e agrega
    em trimestres. Detecta spikes (> mean + 2*std) que podem indicar
    stimulated reporting, litigation ou submissão em lote.

    Args:
        drug: Nome genérico do medicamento.
        event: Termo do evento adverso MedDRA.
        suspect_only: Se True, conta apenas reports onde a droga é suspect.
        use_bulk: None=auto-detect, True=forçar bulk, False=forçar API.
        use_cache: Se deve usar cache.

    Returns:
        TimelineResult com série trimestral e detecção de spikes.
    """
    # --- Bulk path ---
    should_bulk = await _should_use_bulk(use_bulk)
    if should_bulk:
        from hypokrates.faers_bulk.constants import RoleCodFilter
        from hypokrates.faers_bulk.timeline import bulk_signal_timeline

        role_filter = RoleCodFilter.SUSPECT if suspect_only else RoleCodFilter.ALL
        return await bulk_signal_timeline(drug, event, role_filter=role_filter)

    # --- API path ---
    reaction_field = SEARCH_FIELDS["reaction"]
    reaction_query = _build_reaction_query(event, reaction_field)

    client = FAERSClient()
    try:
        drug_search = await resolve_drug_field(drug, client=client, use_cache=use_cache)

        char_filter = (
            f" AND {DRUG_CHARACTERIZATION_FIELD}:{DRUG_CHARACTERIZATION_SUSPECT}"
            if suspect_only
            else ""
        )
        search = f"{drug_search}{char_filter} AND {reaction_query}"
        count_field = COUNT_FIELDS["receivedate"]

        try:
            data = await client.fetch_count(search, count_field, limit=1000, use_cache=use_cache)
        except Exception:
            logger.warning(
                "signal_timeline %s + %s: count query failed, returning empty",
                drug,
                event,
            )
            data = {"results": []}
    finally:
        await client.close()

    raw_results: list[dict[str, Any]] = data.get("results", [])
    quarters = _aggregate_quarterly(raw_results)
    total_reports = sum(q.count for q in quarters)

    # Estatísticas e detecção de spikes
    peak: QuarterlyCount | None = None
    mean_val = 0.0
    std_val = 0.0
    spikes: list[QuarterlyCount] = []

    if quarters:
        counts = [q.count for q in quarters]
        peak = max(quarters, key=lambda q: q.count)
        mean_val = _statistics.mean(counts)
        std_val = _statistics.stdev(counts) if len(counts) >= 2 else 0.0
        if std_val > 0:
            threshold = mean_val + SPIKE_THRESHOLD_SIGMA * std_val
            spikes = [q for q in quarters if q.count > threshold]

    return TimelineResult(
        drug=drug,
        event=event,
        quarters=quarters,
        total_reports=total_reports,
        peak_quarter=peak,
        mean_quarterly=round(mean_val, 1),
        std_quarterly=round(std_val, 1),
        spike_quarters=spikes,
        suspect_only=suspect_only,
        meta=MetaInfo(
            source="OpenFDA/FAERS",
            query={"drug": drug, "event": event, "suspect_only": suspect_only},
            total_results=total_reports,
            retrieved_at=datetime.now(UTC),
            disclaimer="Quarterly aggregation of FAERS receivedate counts. "
            "Spikes may indicate stimulated reporting, not necessarily true signal increase.",
        ),
    )


def _aggregate_quarterly(daily_counts: list[dict[str, Any]]) -> list[QuarterlyCount]:
    """Agrega contagens diárias OpenFDA receivedate em trimestres."""
    quarterly: dict[tuple[int, int], int] = {}
    for entry in daily_counts:
        time_str = str(entry.get("time", ""))
        count = int(entry.get("count", 0))
        if len(time_str) < 6:
            continue
        year = int(time_str[:4])
        month = int(time_str[4:6])
        quarter = (month - 1) // 3 + 1
        key = (year, quarter)
        quarterly[key] = quarterly.get(key, 0) + count

    return [
        QuarterlyCount(year=y, quarter=q, count=c, label=f"{y}-Q{q}")
        for (y, q), c in sorted(quarterly.items())
    ]
