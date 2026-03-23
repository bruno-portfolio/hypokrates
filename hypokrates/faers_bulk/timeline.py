"""Timeline temporal via FAERS Bulk — contagens por quarter deduplicadas."""

from __future__ import annotations

import asyncio
import logging
import statistics as _statistics
from datetime import UTC, datetime

from hypokrates.faers_bulk.constants import RoleCodFilter
from hypokrates.faers_bulk.drug_resolver import resolve_bulk_drug
from hypokrates.faers_bulk.store import FAERSBulkStore
from hypokrates.models import MetaInfo
from hypokrates.stats.constants import SPIKE_THRESHOLD_SIGMA
from hypokrates.stats.models import QuarterlyCount, TimelineResult

logger = logging.getLogger(__name__)

# SQL para contagens trimestrais deduplicadas
_QUARTERLY_COUNTS_SQL = """
WITH deduped AS (
    SELECT primaryid FROM faers_dedup
),
drug_pids AS (
    SELECT DISTINCT d.primaryid
    FROM faers_drug d
    INNER JOIN deduped dd ON d.primaryid = dd.primaryid
    WHERE d.drug_name_norm = ANY($drugs)
    AND (
        $role = 'all'
        OR ($role = 'suspect' AND d.role_cod IN ('PS', 'SS'))
        OR ($role = 'ps_only' AND d.role_cod = 'PS')
    )
),
event_pids AS (
    SELECT DISTINCT r.primaryid
    FROM faers_reac r
    INNER JOIN deduped dd ON r.primaryid = dd.primaryid
    WHERE r.pt_upper = ANY($events)
),
pair_pids AS (
    SELECT dp.primaryid
    FROM drug_pids dp
    INNER JOIN event_pids ep ON dp.primaryid = ep.primaryid
)
SELECT dem.quarter_key, COUNT(DISTINCT pp.primaryid) AS cnt
FROM pair_pids pp
INNER JOIN faers_demo dem ON pp.primaryid = dem.primaryid
GROUP BY dem.quarter_key
ORDER BY dem.quarter_key
"""


async def bulk_signal_timeline(
    drug: str,
    event: str,
    *,
    role_filter: RoleCodFilter = RoleCodFilter.SUSPECT,
) -> TimelineResult:
    """Série temporal trimestral via FAERS Bulk (deduplicado por CASEID).

    Args:
        drug: Nome genérico do medicamento.
        event: Preferred term MedDRA do evento.
        role_filter: Filtro de role (PS_ONLY, SUSPECT, ALL).

    Returns:
        TimelineResult com série trimestral e detecção de spikes.
    """
    store = FAERSBulkStore.get_instance()

    # Resolve drug name
    resolved = await resolve_bulk_drug(drug, store=store)
    drug_name = resolved if resolved is not None else drug.strip().upper()

    # Expandir sinônimos INN/USAN para a droga
    from hypokrates.vocab.drug_synonyms import expand_drug_names

    drug_names = expand_drug_names(drug_name)

    # Expandir sinônimos MedDRA para o evento
    from hypokrates.vocab.meddra import expand_event_terms

    event_terms = expand_event_terms(event)

    # Query no bulk store (thread)
    rows = await asyncio.to_thread(_query_quarterly, store, drug_names, event_terms, role_filter)

    # Converter para QuarterlyCount
    quarters: list[QuarterlyCount] = []
    for quarter_key, count in rows:
        year = int(quarter_key[:4])
        q = int(quarter_key[-1])
        quarters.append(
            QuarterlyCount(
                year=year,
                quarter=q,
                count=count,
                label=f"{year}-Q{q}",
            )
        )

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

    suspect_only = role_filter in (RoleCodFilter.SUSPECT, RoleCodFilter.PS_ONLY)

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
            source="FAERS/bulk (deduplicated)",
            query={
                "drug": drug,
                "event": event,
                "role_filter": role_filter.value,
            },
            total_results=total_reports,
            retrieved_at=datetime.now(UTC),
            disclaimer="Quarterly aggregation of FAERS bulk data, deduplicated by CASEID. "
            "Spikes may indicate stimulated reporting, not necessarily true signal increase.",
        ),
    )


def _query_quarterly(
    store: FAERSBulkStore,
    drug_names: list[str],
    events: list[str],
    role_filter: RoleCodFilter,
) -> list[tuple[str, int]]:
    """Query DuckDB para contagens trimestrais (sync, chamado via to_thread)."""
    with store._db_lock:
        rows = store._conn.execute(
            _QUARTERLY_COUNTS_SQL,
            {"drugs": drug_names, "events": events, "role": role_filter.value},
        ).fetchall()
    return [(str(row[0]), int(row[1])) for row in rows]
