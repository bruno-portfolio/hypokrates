"""API pública do módulo DailyMed — async-first."""

from __future__ import annotations

import logging
from datetime import UTC, datetime

from hypokrates.dailymed.client import DailyMedClient
from hypokrates.dailymed.models import LabelCheckResult, LabelEventsResult
from hypokrates.dailymed.parser import (
    has_safety_sections,
    match_event_in_label,
    parse_adverse_reactions_xml,
    parse_spl_search,
)
from hypokrates.models import MetaInfo

logger = logging.getLogger(__name__)


async def label_events(
    drug: str,
    *,
    use_cache: bool = True,
) -> LabelEventsResult:
    """Extrai eventos adversos da bula FDA (SPL) de uma droga.

    Args:
        drug: Nome da droga.
        use_cache: Se deve usar cache.

    Returns:
        LabelEventsResult com termos de adverse reactions e texto raw.
    """
    client = DailyMedClient()
    try:
        # 1. Buscar SPLs
        search_data = await client.search_spls(drug, use_cache=use_cache)
        set_ids = parse_spl_search(search_data)

        if not set_ids:
            return LabelEventsResult(
                drug=drug,
                meta=MetaInfo(
                    source="DailyMed/FDA",
                    query={"drug": drug},
                    total_results=0,
                    retrieved_at=datetime.now(UTC),
                    disclaimer="No SPL found in DailyMed for this drug.",
                ),
            )

        # 2. Fetch XML — escolher SPL que tenha seções de segurança
        set_id = set_ids[0]
        xml_text = ""
        for candidate_id in set_ids:
            candidate_xml = await client.fetch_spl_xml(candidate_id, use_cache=use_cache)
            if has_safety_sections(candidate_xml):
                set_id = candidate_id
                xml_text = candidate_xml
                break

        # Fallback: usar primeiro SPL se nenhum tem seções de segurança
        if not xml_text:
            xml_text = await client.fetch_spl_xml(set_ids[0], use_cache=use_cache)
            set_id = set_ids[0]

        # 3. Parsear adverse reactions
        terms, raw_text = parse_adverse_reactions_xml(xml_text)
    finally:
        await client.close()

    return LabelEventsResult(
        drug=drug,
        set_id=set_id,
        events=terms,
        raw_text=raw_text,
        meta=MetaInfo(
            source="DailyMed/FDA",
            query={"drug": drug, "set_id": set_id},
            total_results=len(terms),
            retrieved_at=datetime.now(UTC),
            disclaimer="Safety events extracted from FDA SPL label "
            "(Adverse Reactions, Boxed Warning, Warnings and Precautions). "
            "Matching is case-insensitive substring — may include false positives.",
        ),
    )


async def check_label(
    drug: str,
    event: str,
    *,
    use_cache: bool = True,
    _label_cache: LabelEventsResult | None = None,
) -> LabelCheckResult:
    """Verifica se um evento adverso está na bula FDA de uma droga.

    Args:
        drug: Nome da droga.
        event: Termo do evento adverso.
        use_cache: Se deve usar cache.
        _label_cache: Resultado pré-computado de label_events (uso interno
            para evitar N+1 durante scan).

    Returns:
        LabelCheckResult indicando se o evento está na bula.
    """
    result = _label_cache or await label_events(drug, use_cache=use_cache)

    in_label, matched_terms = match_event_in_label(event, result.events, result.raw_text)

    return LabelCheckResult(
        drug=drug,
        event=event,
        in_label=in_label,
        matched_terms=matched_terms,
        set_id=result.set_id,
        meta=MetaInfo(
            source="DailyMed/FDA",
            query={"drug": drug, "event": event},
            total_results=1 if in_label else 0,
            retrieved_at=datetime.now(UTC),
            disclaimer="Label check via DailyMed SPL. "
            "Case-insensitive substring matching — clinical validation required.",
        ),
    )
