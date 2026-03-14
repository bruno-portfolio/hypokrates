"""API pública de detecção de sinais — async-first."""

from __future__ import annotations

import logging
from datetime import UTC, datetime

from hypokrates.faers.api import resolve_drug_field
from hypokrates.faers.client import FAERSClient
from hypokrates.faers.constants import SEARCH_FIELDS
from hypokrates.models import MetaInfo
from hypokrates.stats.constants import MIN_MEASURES_FOR_SIGNAL, MIN_REPORT_COUNT, SIGNAL_DISCLAIMER
from hypokrates.stats.measures import build_table, compute_ic, compute_prr, compute_ror
from hypokrates.stats.models import SignalResult

logger = logging.getLogger(__name__)


async def signal(
    drug: str,
    event: str,
    *,
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
        use_cache: Se deve usar cache.

    Returns:
        SignalResult com PRR, ROR, IC e heurística signal_detected.
    """
    reaction_field = SEARCH_FIELDS["reaction"]
    event_upper = event.upper()

    client = FAERSClient()
    try:
        drug_search = await resolve_drug_field(drug, client=client, use_cache=use_cache)

        search_drug_event = f'{drug_search} AND {reaction_field}:"{event_upper}"'
        search_drug = drug_search
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
