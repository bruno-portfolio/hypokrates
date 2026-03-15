"""API pública do módulo OpenTargets — async-first."""

from __future__ import annotations

import logging
from datetime import UTC, datetime

from hypokrates.models import MetaInfo
from hypokrates.opentargets.client import OpenTargetsClient
from hypokrates.opentargets.constants import DRUG_ADVERSE_EVENTS_QUERY, SEARCH_DRUG_QUERY
from hypokrates.opentargets.models import OTDrugSafety
from hypokrates.opentargets.parser import (
    parse_adverse_events,
    parse_adverse_events_meta,
    parse_search_drug,
)

logger = logging.getLogger(__name__)


async def drug_adverse_events(
    drug_name: str,
    *,
    use_cache: bool = True,
) -> OTDrugSafety:
    """Busca adverse events de uma droga no OpenTargets.

    Resolve drug name → ChEMBL ID, depois busca adverseEvents.

    Args:
        drug_name: Nome da droga.
        use_cache: Se deve usar cache.

    Returns:
        OTDrugSafety com lista de adverse events e LRT scores.
    """
    client = OpenTargetsClient()
    try:
        # 1. Resolver nome → ChEMBL ID
        search_data = await client.query(
            SEARCH_DRUG_QUERY,
            {"name": drug_name},
            use_cache=use_cache,
        )
        chembl_id = parse_search_drug(search_data)

        if not chembl_id:
            logger.info("OpenTargets: drug '%s' not found", drug_name)
            return OTDrugSafety(
                drug_name=drug_name,
                chembl_id="",
                meta=MetaInfo(
                    source="OpenTargets",
                    query={"drug": drug_name},
                    total_results=0,
                    retrieved_at=datetime.now(UTC),
                    disclaimer="Drug not found in OpenTargets Platform.",
                ),
            )

        # 2. Buscar adverse events
        ae_data = await client.query(
            DRUG_ADVERSE_EVENTS_QUERY,
            {"chemblId": chembl_id},
            use_cache=use_cache,
        )

        events = parse_adverse_events(ae_data)
        total_count, critical_value = parse_adverse_events_meta(ae_data)

        return OTDrugSafety(
            drug_name=drug_name,
            chembl_id=chembl_id,
            adverse_events=events,
            total_count=total_count,
            critical_value=critical_value,
            meta=MetaInfo(
                source="OpenTargets",
                query={"drug": drug_name, "chembl_id": chembl_id},
                total_results=total_count,
                retrieved_at=datetime.now(UTC),
                disclaimer="Adverse events from OpenTargets Platform (FAERS-based LRT analysis). "
                "LRT score indicates statistical association, not causation.",
            ),
        )
    finally:
        await client.close()


async def drug_safety_score(
    drug_name: str,
    event: str,
    *,
    use_cache: bool = True,
    _safety_cache: OTDrugSafety | None = None,
) -> float | None:
    """Retorna LRT score de um par droga-evento no OpenTargets.

    Args:
        drug_name: Nome da droga.
        event: Termo do evento adverso.
        use_cache: Se deve usar cache.
        _safety_cache: Cache de OTDrugSafety (para evitar re-fetch no scan).

    Returns:
        log-likelihood ratio ou None se não encontrado.
    """
    if _safety_cache is not None:
        safety = _safety_cache
    else:
        safety = await drug_adverse_events(drug_name, use_cache=use_cache)

    if not safety.adverse_events:
        return None

    # Match case-insensitive, com expansão MedDRA
    from hypokrates.vocab.meddra import expand_event_terms

    event_terms = {t.upper().strip() for t in expand_event_terms(event)}
    best_score: float | None = None
    for ae in safety.adverse_events:
        if ae.name.upper().strip() in event_terms and (
            best_score is None or ae.log_lr > best_score
        ):
            best_score = ae.log_lr

    return best_score
