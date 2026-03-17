"""Parsers para respostas DailyMed (JSON + SPL XML)."""

from __future__ import annotations

import logging
import re
import xml.etree.ElementTree as ET
from typing import Any, TypedDict

from hypokrates.dailymed.constants import SAFETY_LOINC_CODES, SPL_NAMESPACE

logger = logging.getLogger(__name__)


class SPLCandidate(TypedDict):
    """Candidato SPL com metadata para ranking."""

    setid: str
    title: str
    spl_version: int


# Palavras no título que indicam label veterinário
_VET_MARKERS: set[str] = {
    "VETERINARY",
    "COVETRUS",
    "DECHRA",
    "HENRY SCHEIN ANIMAL",
    "VET ",
    "VEDCO",
    "BIMEDA",
    "ZOETIS",
    "ELANCO",
}

# Formas farmacêuticas prescription (mais relevantes para farmacovigilância)
_PRESCRIPTION_FORMS: set[str] = {
    "INJECTION",
    "INJECTABLE",
    "TABLET",
    "CAPSULE",
    "ORAL SOLUTION",
    "ORAL SUSPENSION",
    "INTRAVENOUS",
    "INFUSION",
    "CONCENTRATE",
    "SUPPOSITORY",
    "INHALATION",
}

# Marcadores de produto combinado (múltiplos ingredientes ativos)
_COMBINATION_MARKERS: list[str] = [" AND ", " WITH ", " / "]

# Formas farmacêuticas OTC tópicas (menos relevantes)
_OTC_TOPICAL_FORMS: set[str] = {
    "PATCH",
    "PATCHES",
    "CREAM",
    "GEL ",
    "OINTMENT",
    "LOTION",
    "SPRAY",
    "TOPICAL",
    "WIPE",
    "ROLL-ON",
    "MENTHOL",
    "PAIN RELIEF",
    "PAIN RELIEVING",
}


def _score_spl_candidate(candidate: SPLCandidate) -> int:
    # Higher score = more relevant for PV. Favors single-ingredient, systemic, prescription.
    title_upper = candidate["title"].upper()
    score = min(candidate["spl_version"], 5)

    for marker in _VET_MARKERS:
        if marker in title_upper:
            return -100

    for pattern in _COMBINATION_MARKERS:
        if pattern in title_upper:
            score -= 50
            break

    for form in _PRESCRIPTION_FORMS:
        if form in title_upper:
            score += 25
            break

    for form in _OTC_TOPICAL_FORMS:
        if form in title_upper:
            score -= 25
            break

    return score


def _is_combination_title(title: str) -> bool:
    title_upper = title.upper()
    return any(marker in title_upper for marker in _COMBINATION_MARKERS)


def parse_spl_search(data: dict[str, Any]) -> tuple[list[str], list[str]]:
    """Extrai SET IDs rankeados, separando singles de combos."""
    results = data.get("data", [])
    candidates: list[SPLCandidate] = []
    for item in results:
        set_id = item.get("setid")
        if isinstance(set_id, str) and set_id:
            title = item.get("title", "")
            spl_version = int(item.get("spl_version", 1))
            candidates.append(
                SPLCandidate(
                    setid=set_id,
                    title=title if isinstance(title, str) else "",
                    spl_version=spl_version,
                )
            )

    candidates.sort(key=_score_spl_candidate, reverse=True)

    singles: list[str] = []
    combos: list[str] = []
    for c in candidates:
        if _is_combination_title(c["title"]):
            combos.append(c["setid"])
        else:
            singles.append(c["setid"])

    return singles, combos


def parse_adverse_reactions_xml(xml_text: str) -> tuple[list[str], str]:
    """Extrai termos de safety sections (LOINC) de um SPL XML."""
    try:
        root = ET.fromstring(xml_text)
    except ET.ParseError:
        logger.warning("Failed to parse SPL XML")
        return [], ""

    all_text_parts: list[str] = []
    for loinc_code in SAFETY_LOINC_CODES:
        section_text = _find_section_by_loinc(root, loinc_code)
        if section_text:
            all_text_parts.append(section_text)

    if not all_text_parts:
        return [], ""

    combined_text = "\n".join(all_text_parts)
    terms = _extract_terms(combined_text)
    return terms, combined_text


_FUZZY_THRESHOLD = 85  # rapidfuzz token_sort_ratio threshold


def match_event_in_label(
    event: str,
    terms: list[str],
    raw_text: str = "",
) -> tuple[bool, list[str]]:
    """Multi-layer matching: substring, MedDRA synonyms, fuzzy (token_sort_ratio>=85)."""
    from hypokrates.vocab.meddra import expand_event_terms

    search_terms = expand_event_terms(event)

    matched: list[str] = []

    for search_event in search_terms:
        event_lower = search_event.lower()
        for term in terms:
            term_lower = term.lower()
            is_match = event_lower in term_lower or term_lower in event_lower
            if is_match and term not in matched:
                matched.append(term)

    if matched:
        return True, matched

    for search_event in search_terms:
        event_words = set(search_event.lower().split())
        if len(event_words) < 2:
            continue  # single-word already covered by substring
        for term in terms:
            term_lower = term.lower()
            if all(w in term_lower for w in event_words) and term not in matched:
                matched.append(term)
    if matched:
        return True, matched

    if raw_text:
        raw_lower = raw_text.lower()
        for search_event in search_terms:
            if search_event.lower() in raw_lower:
                matched.append(search_event)
                return True, matched

    # All-words-present in raw_text (catches cross-section multi-word events)
    if raw_text:
        raw_lower = raw_text.lower()
        for search_event in search_terms:
            event_words = set(search_event.lower().split())
            if len(event_words) >= 2 and all(w in raw_lower for w in event_words):
                matched.append(search_event)
                return True, matched

    try:
        from rapidfuzz.fuzz import token_sort_ratio  # type: ignore[import-not-found,unused-ignore]
    except ImportError:
        return False, []

    for search_event in search_terms:
        for term in terms:
            score: float = token_sort_ratio(search_event.lower(), term.lower())
            if score >= _FUZZY_THRESHOLD and term not in matched:
                matched.append(term)

    if not matched and raw_text:
        sentences = re.split(r"[.;,\n]+", raw_text)
        for search_event in search_terms:
            for sentence in sentences:
                sentence = sentence.strip()
                if len(sentence) < 3:
                    continue
                score = token_sort_ratio(search_event.lower(), sentence.lower())
                if score >= _FUZZY_THRESHOLD:
                    matched.append(search_event)
                    break
            if matched:
                break

    return len(matched) > 0, matched


def parse_indications_text(xml_text: str) -> str:
    """Extrai texto da secao INDICATIONS AND USAGE (LOINC 34067-9)."""
    from hypokrates.dailymed.constants import INDICATIONS_LOINC

    try:
        root = ET.fromstring(xml_text)
    except ET.ParseError:
        return ""

    return _find_section_by_loinc(root, INDICATIONS_LOINC)


def has_adverse_reactions_section(xml_text: str) -> bool:
    """Verifica se SPL contem secao Adverse Reactions (LOINC 34084-4)."""
    try:
        root = ET.fromstring(xml_text)
    except ET.ParseError:
        return False

    from hypokrates.dailymed.constants import ADVERSE_REACTIONS_LOINC

    section_text = _find_section_by_loinc(root, ADVERSE_REACTIONS_LOINC)
    return bool(section_text)


def has_safety_sections(xml_text: str) -> bool:
    """Verifica se SPL contem pelo menos uma secao de seguranca (LOINC)."""
    try:
        root = ET.fromstring(xml_text)
    except ET.ParseError:
        return False

    for loinc_code in SAFETY_LOINC_CODES:
        section_text = _find_section_by_loinc(root, loinc_code)
        if section_text:
            return True
    return False


def _find_section_by_loinc(root: ET.Element, loinc_code: str) -> str:
    ns = SPL_NAMESPACE

    for component in root.iter(f"{ns}component"):
        for section in component.iter(f"{ns}section"):
            code_elem = section.find(f"{ns}code")
            if code_elem is not None:
                code_val = code_elem.get("code", "")
                if code_val == loinc_code:
                    return _extract_text_from_section(section)

    return ""


def _extract_text_from_section(section: ET.Element) -> str:
    ns = SPL_NAMESPACE
    parts: list[str] = []

    for text_elem in section.iter(f"{ns}text"):
        raw = ET.tostring(text_elem, encoding="unicode", method="text")
        if raw:
            parts.append(raw.strip())

    if not parts:
        for para in section.iter(f"{ns}paragraph"):
            raw = ET.tostring(para, encoding="unicode", method="text")
            if raw:
                parts.append(raw.strip())

    return "\n".join(parts)


def _extract_terms(text: str) -> list[str]:
    normalized = re.sub(r"[;,\n\r]+", "|", text)
    raw_terms = normalized.split("|")

    terms: list[str] = []
    for raw in raw_terms:
        term = raw.strip()
        if len(term) < 3:
            continue
        if term.replace(".", "").replace("%", "").isdigit():
            continue
        terms.append(term)

    return terms
