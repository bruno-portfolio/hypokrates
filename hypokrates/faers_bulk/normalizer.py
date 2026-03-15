"""Normalização de nomes de droga para FAERS Bulk.

Tier 1: prod_ai (Active Ingredient padronizado pela FDA) — cobre ~85% pós-2014.
Tier 2: drugname limpo (remove dose, pontuação) — fallback para campos não-padronizados.
"""

from __future__ import annotations

import re

# Regex para remover informação de dose trailing
# Exemplos: "PROPOFOL 10MG/ML" → "PROPOFOL", "FENTANYL 50 MCG" → "FENTANYL"
_DOSE_PATTERN = re.compile(
    r"\s+\d+[\d.,]*\s*(?:MG|MCG|UG|G|ML|L|IU|UNITS?|%|MG/ML|MCG/ML|MG/KG)(?:/\S+)?\s*$",
    re.IGNORECASE,
)

# Caracteres a limpar do final
_TRAILING_PUNCT = re.compile(r"[.,;:\s]+$")

# Valores que significam "vazio" no FAERS ASCII
_EMPTY_VALUES = frozenset({"", "\\N", "\\n", "NA", "N/A", "NONE", "."})


def normalize_drug_name(prod_ai: str, drugname: str) -> str:
    """Normaliza nome de droga usando hierarquia prod_ai > drugname.

    Args:
        prod_ai: Campo ``prod_ai`` do DRUG file (Active Ingredient padronizado).
        drugname: Campo ``drugname`` do DRUG file (texto livre do reporter).

    Returns:
        Nome normalizado em UPPER, ou string vazia se ambos os campos vazios.
    """
    # Tier 1: prod_ai tem prioridade (padronizado pela FDA)
    cleaned = _clean_drug_text(prod_ai)
    if cleaned:
        return cleaned

    # Tier 2: drugname com limpeza de dose
    cleaned = _clean_drug_text(drugname)
    if cleaned:
        # Remove dose info que frequentemente aparece em drugname
        cleaned = _DOSE_PATTERN.sub("", cleaned)
        cleaned = _TRAILING_PUNCT.sub("", cleaned)
    return cleaned


def _clean_drug_text(raw: str) -> str:
    """Limpa texto de droga: upper, strip, handle vazios.

    Args:
        raw: Texto bruto do campo.

    Returns:
        Texto limpo em UPPER, ou string vazia.
    """
    if not raw:
        return ""
    text = raw.strip().upper()
    if text in _EMPTY_VALUES:
        return ""
    # Remove pontuação trailing
    text = _TRAILING_PUNCT.sub("", text)
    return text
