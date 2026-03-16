"""API pública do módulo DailyMed — async-first."""

from __future__ import annotations

import logging
from datetime import UTC, datetime

from hypokrates.dailymed.client import DailyMedClient
from hypokrates.dailymed.models import LabelCheckResult, LabelEventsResult
from hypokrates.dailymed.parser import (
    has_adverse_reactions_section,
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
    async with DailyMedClient() as client:
        # 1. Buscar SPLs — separados em singles e combos
        search_data = await client.search_spls(drug, use_cache=use_cache)
        single_ids, combo_ids = parse_spl_search(search_data)
        all_ids = single_ids + combo_ids

        if not all_ids:
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

        # 2. Fetch XML — seleção em 4 passadas
        #    Prioriza single-ingredient sobre combos para evitar
        #    ex: acetaminophen+codeine quando buscando acetaminophen.
        #    Pass 1: single com AR section (34084-4)
        #    Pass 2: single com qualquer seção de segurança
        #    Pass 3: combo com AR section
        #    Pass 4: combo com qualquer seção de segurança
        set_id = all_ids[0]
        xml_text = ""
        fetched_xmls: dict[str, str] = {}

        async def _fetch(cid: str) -> str:
            if cid in fetched_xmls:
                return fetched_xmls[cid]
            xml = await client.fetch_spl_xml(cid, use_cache=use_cache)
            fetched_xmls[cid] = xml
            return xml

        # Pass 1+2: singles first
        for candidate_id in single_ids:
            candidate_xml = await _fetch(candidate_id)
            if has_adverse_reactions_section(candidate_xml):
                set_id = candidate_id
                xml_text = candidate_xml
                break

        if not xml_text:
            for candidate_id in single_ids:
                candidate_xml = fetched_xmls.get(candidate_id, "")
                if candidate_xml and has_safety_sections(candidate_xml):
                    set_id = candidate_id
                    xml_text = candidate_xml
                    break

        # Pass 3+4: combos fallback
        if not xml_text:
            for candidate_id in combo_ids:
                candidate_xml = await _fetch(candidate_id)
                if has_adverse_reactions_section(candidate_xml):
                    set_id = candidate_id
                    xml_text = candidate_xml
                    break

        if not xml_text:
            for candidate_id in combo_ids:
                candidate_xml = fetched_xmls.get(candidate_id, "")
                if candidate_xml and has_safety_sections(candidate_xml):
                    set_id = candidate_id
                    xml_text = candidate_xml
                    break

        # Fallback: usar primeiro SPL se nenhum tem seções de segurança
        if not xml_text:
            xml_text = fetched_xmls.get(all_ids[0], "")
            if not xml_text:
                xml_text = await client.fetch_spl_xml(all_ids[0], use_cache=use_cache)
            set_id = all_ids[0]

        # 3. Parsear adverse reactions
        terms, raw_text = parse_adverse_reactions_xml(xml_text)

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
