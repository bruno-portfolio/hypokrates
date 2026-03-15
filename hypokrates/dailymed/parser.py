"""Parsers para respostas DailyMed (JSON + SPL XML)."""

from __future__ import annotations

import logging
import re
import xml.etree.ElementTree as ET
from typing import Any

from hypokrates.dailymed.constants import SAFETY_LOINC_CODES, SPL_NAMESPACE

logger = logging.getLogger(__name__)


def parse_spl_search(data: dict[str, Any]) -> list[str]:
    """Extrai SET IDs de uma resposta de busca DailyMed.

    Args:
        data: JSON response de /spls.json.

    Returns:
        Lista de set_id strings.
    """
    results = data.get("data", [])
    set_ids: list[str] = []
    for item in results:
        set_id = item.get("setid")
        if isinstance(set_id, str) and set_id:
            set_ids.append(set_id)
    return set_ids


def parse_adverse_reactions_xml(xml_text: str) -> tuple[list[str], str]:
    """Extrai termos de safety sections de um SPL XML.

    Busca seções de Adverse Reactions, Boxed Warning, Warnings, e
    Warnings and Precautions pelo LOINC code e extrai termos textuais.

    Args:
        xml_text: XML completo do SPL.

    Returns:
        Tupla (lista de termos normalizados, texto raw combinado das seções).
    """
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
    """Verifica se um evento adverso está presente nos termos da bula.

    3 camadas de matching:
    1. Substring case-insensitive (rápido, sem falsos positivos)
    2. MedDRA synonyms — expande para canonical+aliases e retenta substring
    3. Fuzzy — rapidfuzz token_sort_ratio >= 85 (pega ordem invertida,
       grafias BrE/AmE como apnoea/apnea, variações menores)

    Args:
        event: Termo do evento adverso (e.g., "bradycardia").
        terms: Lista de termos extraídos da bula.
        raw_text: Texto raw da seção (fallback).

    Returns:
        Tupla (encontrado, lista de termos matched).
    """
    from hypokrates.vocab.meddra import expand_event_terms

    # Expandir evento para incluir sinônimos MedDRA (canonical + aliases)
    search_terms = expand_event_terms(event)

    matched: list[str] = []

    # Layer 1 + 2: substring match (original + MedDRA synonyms)
    for search_event in search_terms:
        event_lower = search_event.lower()
        for term in terms:
            term_lower = term.lower()
            is_match = event_lower in term_lower or term_lower in event_lower
            if is_match and term not in matched:
                matched.append(term)

    if matched:
        return True, matched

    # Layer 2 fallback: buscar no texto raw com todos os sinônimos
    if raw_text:
        raw_lower = raw_text.lower()
        for search_event in search_terms:
            if search_event.lower() in raw_lower:
                matched.append(search_event)
                return True, matched

    # Layer 3: fuzzy matching com rapidfuzz
    try:
        from rapidfuzz.fuzz import token_sort_ratio  # type: ignore[import-not-found,unused-ignore]
    except ImportError:
        return False, []

    for search_event in search_terms:
        for term in terms:
            score: float = token_sort_ratio(search_event.lower(), term.lower())
            if score >= _FUZZY_THRESHOLD and term not in matched:
                matched.append(term)

    # Fuzzy no raw_text: split em sentenças e comparar
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


def has_safety_sections(xml_text: str) -> bool:
    """Verifica se um SPL XML contém pelo menos uma seção de segurança (LOINC).

    Usado para filtrar SPLs irrelevantes (ex: powder, OTC, patch) que não
    têm seções de Adverse Reactions ou Warnings.

    Args:
        xml_text: XML completo do SPL.

    Returns:
        True se pelo menos um LOINC de segurança foi encontrado.
    """
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
    """Busca seção SPL por LOINC code."""
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
    """Extrai todo o texto de uma seção SPL (incluindo sub-elementos)."""
    ns = SPL_NAMESPACE
    parts: list[str] = []

    for text_elem in section.iter(f"{ns}text"):
        raw = ET.tostring(text_elem, encoding="unicode", method="text")
        if raw:
            parts.append(raw.strip())

    # Fallback: pegar paragraphs apenas se <text> não produziu conteúdo
    if not parts:
        for para in section.iter(f"{ns}paragraph"):
            raw = ET.tostring(para, encoding="unicode", method="text")
            if raw:
                parts.append(raw.strip())

    return "\n".join(parts)


def _extract_terms(text: str) -> list[str]:
    """Extrai termos individuais de adverse reactions do texto da bula.

    Estratégia: split por vírgulas, ponto-e-vírgula, e newlines.
    Filtra tokens muito curtos ou numéricos.
    """
    # Normalizar separadores
    normalized = re.sub(r"[;,\n\r]+", "|", text)
    raw_terms = normalized.split("|")

    terms: list[str] = []
    for raw in raw_terms:
        term = raw.strip()
        # Filtrar tokens muito curtos, numéricos, ou boilerplate
        if len(term) < 3:
            continue
        if term.replace(".", "").replace("%", "").isdigit():
            continue
        terms.append(term)

    return terms
