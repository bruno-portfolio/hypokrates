"""Parsers para respostas de RxNorm e MeSH APIs."""

from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)


def parse_rxnorm_drugs(data: dict[str, Any]) -> tuple[str | None, list[str], str | None]:
    """Parseia resposta do RxNorm /drugs.json.

    Args:
        data: JSON response do RxNorm.

    Returns:
        Tupla (generic_name, brand_names, rxcui).
    """
    drug_group = data.get("drugGroup", {})
    concept_groups = drug_group.get("conceptGroup", [])

    generic_name: str | None = None
    brand_names: list[str] = []
    rxcui: str | None = None

    for group in concept_groups:
        tty = group.get("tty", "")
        concepts = group.get("conceptProperties", [])
        if not concepts:
            continue

        if tty == "IN":
            # Ingredient — nome genérico
            first = concepts[0]
            generic_name = first.get("name")
            rxcui = first.get("rxcui")
        elif tty == "BN":
            # Brand Name
            for concept in concepts:
                name = concept.get("name")
                if name:
                    brand_names.append(name)
        elif tty in ("SBD", "SCD") and generic_name is None:
            # Semantic Branded Drug / Semantic Clinical Drug — extrair ingredient
            # Ex: "Diprivan 10 MG/ML Injectable Emulsion" → parse para obter ingredient
            first = concepts[0]
            rxcui = rxcui or first.get("rxcui")

    return generic_name, brand_names, rxcui


def parse_rxcui_response(data: dict[str, Any]) -> str | None:
    """Parseia resposta do RxNorm /rxcui.json para extrair RXCUI.

    Args:
        data: JSON response do /rxcui.json.

    Returns:
        RXCUI string ou None se não encontrado.
    """
    id_group = data.get("idGroup", {})
    rxnorm_id_list = id_group.get("rxnormId", [])
    if rxnorm_id_list:
        return str(rxnorm_id_list[0])
    return None


def parse_allrelated_ingredient(data: dict[str, Any]) -> tuple[str | None, str | None]:
    """Extrai nome genérico (IN) de uma resposta allrelated.

    Args:
        data: JSON response do /rxcui/{id}/allrelated.json.

    Returns:
        Tupla (generic_name, rxcui) do ingredient.
    """
    all_related = data.get("allRelatedGroup", {})
    concept_groups = all_related.get("conceptGroup", [])

    for group in concept_groups:
        tty = group.get("tty", "")
        concepts = group.get("conceptProperties", [])
        if not concepts:
            continue
        if tty == "IN":
            first = concepts[0]
            return first.get("name"), first.get("rxcui")

    return None, None


def parse_mesh_search(data: dict[str, Any]) -> list[str]:
    """Parseia resposta do ESearch db=mesh.

    Args:
        data: JSON response do ESearch.

    Returns:
        Lista de UIDs encontrados.
    """
    esearch = data.get("esearchresult", {})
    id_list: list[str] = esearch.get("idlist", [])
    return id_list


def parse_mesh_descriptor(data: dict[str, Any]) -> tuple[str | None, str | None, list[str]]:
    """Parseia resposta do ESummary db=mesh.

    Args:
        data: JSON response do ESummary.

    Returns:
        Tupla (mesh_id, mesh_term, tree_numbers).
    """
    result_block = data.get("result", {})
    uids: list[str] = result_block.get("uids", [])

    if not uids:
        return None, None, []

    uid = uids[0]
    doc = result_block.get(uid)
    if doc is None or not isinstance(doc, dict):
        return None, None, []

    mesh_id = doc.get("ds_meshui")
    mesh_terms = doc.get("ds_meshterms", [])
    mesh_term: str | None = mesh_terms[0] if mesh_terms else None

    tree_numbers: list[str] = doc.get("ds_treenumberlist", [])

    return mesh_id, mesh_term, tree_numbers
