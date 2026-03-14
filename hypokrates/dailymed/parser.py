"""Parsers para respostas DailyMed (JSON + SPL XML)."""

from __future__ import annotations

import logging
import re
import xml.etree.ElementTree as ET
from typing import Any

from hypokrates.dailymed.constants import ADVERSE_REACTIONS_LOINC, SPL_NAMESPACE

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
    """Extrai termos de adverse reactions de um SPL XML.

    Busca a seção com LOINC code 34084-4 (Adverse Reactions) e extrai
    os termos textuais encontrados.

    Args:
        xml_text: XML completo do SPL.

    Returns:
        Tupla (lista de termos normalizados, texto raw da seção).
    """
    try:
        root = ET.fromstring(xml_text)
    except ET.ParseError:
        logger.warning("Failed to parse SPL XML")
        return [], ""

    # Buscar seção de adverse reactions pelo LOINC code
    section_text = _find_adverse_reactions_section(root)
    if not section_text:
        return [], ""

    # Extrair termos individuais do texto
    terms = _extract_terms(section_text)
    return terms, section_text


def match_event_in_label(
    event: str,
    terms: list[str],
    raw_text: str = "",
) -> tuple[bool, list[str]]:
    """Verifica se um evento adverso está presente nos termos da bula.

    Matching case-insensitive por substring.

    Args:
        event: Termo do evento adverso (e.g., "bradycardia").
        terms: Lista de termos extraídos da bula.
        raw_text: Texto raw da seção (fallback).

    Returns:
        Tupla (encontrado, lista de termos matched).
    """
    event_lower = event.lower()
    matched: list[str] = []

    for term in terms:
        if event_lower in term.lower() or term.lower() in event_lower:
            matched.append(term)

    # Fallback: buscar no texto raw se não encontrou nos termos
    if not matched and raw_text and event_lower in raw_text.lower():
        matched.append(event)

    return len(matched) > 0, matched


def _find_adverse_reactions_section(root: ET.Element) -> str:
    """Busca seção de adverse reactions em SPL XML pelo LOINC code."""
    # SPL usa namespace hl7-org:v3
    ns = SPL_NAMESPACE

    for component in root.iter(f"{ns}component"):
        for section in component.iter(f"{ns}section"):
            code_elem = section.find(f"{ns}code")
            if code_elem is not None:
                code_val = code_elem.get("code", "")
                if code_val == ADVERSE_REACTIONS_LOINC:
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
