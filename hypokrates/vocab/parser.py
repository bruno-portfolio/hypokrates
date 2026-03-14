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

    return generic_name, brand_names, rxcui


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
