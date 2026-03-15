"""API pública de detecção de sinais — async-first."""

from __future__ import annotations

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

logger = logging.getLogger(__name__)


async def signal(
    drug: str,
    event: str,
    *,
    suspect_only: bool = False,
    use_cache: bool = True,
) -> SignalResult:
    """Calcula sinal de desproporcionalidade para um par droga-evento.

    Busca contagens no FAERS e calcula PRR, ROR e IC (simplified).

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
        use_cache: Se deve usar cache.

    Returns:
        SignalResult com PRR, ROR, IC e heurística signal_detected.
    """
    reaction_field = SEARCH_FIELDS["reaction"]
    event_upper = event.upper()

    client = FAERSClient()
    try:
        drug_search = await resolve_drug_field(drug, client=client, use_cache=use_cache)

        char_filter = (
            f" AND {DRUG_CHARACTERIZATION_FIELD}:{DRUG_CHARACTERIZATION_SUSPECT}"
            if suspect_only
            else ""
        )
        search_drug_event = f'{drug_search}{char_filter} AND {reaction_field}:"{event_upper}"'
        search_drug = f"{drug_search}{char_filter}"
        search_event = f'{reaction_field}:"{event_upper}"'

        drug_event_count = await client.fetch_total(search_drug_event, use_cache=use_cache)
        drug_total = await client.fetch_total(search_drug, use_cache=use_cache)
        event_total = await client.fetch_total(search_event, use_cache=use_cache)
        n_total = await client.fetch_total("", use_cache=use_cache)
    finally:
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


async def signal_timeline(
    drug: str,
    event: str,
    *,
    suspect_only: bool = False,
    use_cache: bool = True,
) -> TimelineResult:
    """Série temporal trimestral de reports FAERS para um par droga-evento.

    Usa OpenFDA count=receivedate para obter contagens diárias e agrega
    em trimestres. Detecta spikes (> mean + 2*std) que podem indicar
    stimulated reporting, litigation ou submissão em lote.

    Args:
        drug: Nome genérico do medicamento.
        event: Termo do evento adverso MedDRA.
        suspect_only: Se True, conta apenas reports onde a droga é suspect.
        use_cache: Se deve usar cache.

    Returns:
        TimelineResult com série trimestral e detecção de spikes.
    """
    reaction_field = SEARCH_FIELDS["reaction"]
    event_upper = event.upper()

    client = FAERSClient()
    try:
        drug_search = await resolve_drug_field(drug, client=client, use_cache=use_cache)

        char_filter = (
            f" AND {DRUG_CHARACTERIZATION_FIELD}:{DRUG_CHARACTERIZATION_SUSPECT}"
            if suspect_only
            else ""
        )
        search = f'{drug_search}{char_filter} AND {reaction_field}:"{event_upper}"'
        count_field = COUNT_FIELDS["receivedate"]

        data = await client.fetch_count(search, count_field, limit=1000, use_cache=use_cache)
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
