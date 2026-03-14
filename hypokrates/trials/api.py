"""API pública do módulo ClinicalTrials.gov — async-first."""

from __future__ import annotations

import logging
from datetime import UTC, datetime

from hypokrates.models import MetaInfo
from hypokrates.trials.client import TrialsClient
from hypokrates.trials.models import TrialsResult
from hypokrates.trials.parser import count_active, parse_studies

logger = logging.getLogger(__name__)


async def search_trials(
    drug: str,
    event: str,
    *,
    page_size: int = 10,
    use_cache: bool = True,
) -> TrialsResult:
    """Busca trials clínicos relacionados a um par droga-evento.

    Args:
        drug: Nome da droga.
        event: Termo do evento adverso.
        page_size: Máximo de resultados.
        use_cache: Se deve usar cache.

    Returns:
        TrialsResult com trials encontrados e contagem de ativos.
    """
    client = TrialsClient()
    try:
        data = await client.search(drug, event, page_size=page_size, use_cache=use_cache)
    finally:
        await client.close()

    total_count, trials = parse_studies(data)
    active_count = count_active(trials)

    return TrialsResult(
        drug=drug,
        event=event,
        total_count=total_count,
        active_count=active_count,
        trials=trials,
        meta=MetaInfo(
            source="ClinicalTrials.gov",
            query={"drug": drug, "event": event},
            total_results=total_count,
            retrieved_at=datetime.now(UTC),
            disclaimer="Clinical trials data from ClinicalTrials.gov. "
            "Trial count does not imply established association.",
        ),
    )
