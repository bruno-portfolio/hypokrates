"""Parser de respostas GraphQL do OpenTargets."""

from __future__ import annotations

from typing import Any

from hypokrates.opentargets.models import OTAdverseEvent


def parse_search_drug(data: dict[str, Any]) -> str | None:
    """Extrai ChEMBL ID de uma resposta de search.

    Args:
        data: Resposta GraphQL (campo 'data').

    Returns:
        ChEMBL ID ou None se não encontrado.
    """
    search = data.get("search")
    if search is None:
        return None
    hits = search.get("hits", [])
    if not hits:
        return None
    return str(hits[0].get("id", ""))


def parse_adverse_events(data: dict[str, Any]) -> list[OTAdverseEvent]:
    """Extrai lista de adverse events de uma resposta de drug.adverseEvents.

    Args:
        data: Resposta GraphQL (campo 'data').

    Returns:
        Lista de OTAdverseEvent.
    """
    drug = data.get("drug")
    if drug is None:
        return []

    ae_data = drug.get("adverseEvents")
    if ae_data is None:
        return []

    rows = ae_data.get("rows", [])
    events: list[OTAdverseEvent] = []
    for row in rows:
        events.append(
            OTAdverseEvent(
                name=row.get("name", ""),
                count=row.get("count", 0),
                log_lr=row.get("logLR", 0.0),
                meddra_code=row.get("meddraCode"),
            )
        )

    return events


def parse_adverse_events_meta(data: dict[str, Any]) -> tuple[int, float]:
    """Extrai count e critical value de uma resposta de drug.adverseEvents.

    Returns:
        Tuple (total_count, critical_value).
    """
    drug = data.get("drug")
    if drug is None:
        return 0, 0.0

    ae_data = drug.get("adverseEvents")
    if ae_data is None:
        return 0, 0.0

    return ae_data.get("count", 0), ae_data.get("criticalValue", 0.0)
