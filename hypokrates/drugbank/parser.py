"""Parser streaming de XML do DrugBank via iterparse.

Processa XML de ~175MB com memory footprint baixo usando elem.clear().
"""

from __future__ import annotations

import logging
import xml.etree.ElementTree as ET
from typing import Any

from hypokrates.drugbank.constants import (
    TAG_ACTION,
    TAG_ACTIONS,
    TAG_CATEGORIES,
    TAG_CATEGORY,
    TAG_DESCRIPTION,
    TAG_DRUG,
    TAG_DRUGBANK_ID,
    TAG_ENZYME,
    TAG_ENZYMES,
    TAG_GENE_NAME,
    TAG_INTERACTION,
    TAG_INTERACTIONS,
    TAG_MECHANISM,
    TAG_NAME,
    TAG_ORGANISM,
    TAG_PHARMACODYNAMICS,
    TAG_POLYPEPTIDE,
    TAG_SYNONYM,
    TAG_SYNONYMS,
    TAG_TARGET,
    TAG_TARGETS,
)

logger = logging.getLogger(__name__)


def _text(elem: ET.Element | None) -> str:
    """Extrai texto de um elemento, retornando '' se None."""
    if elem is None:
        return ""
    return (elem.text or "").strip()


def _parse_target(target_elem: ET.Element) -> dict[str, Any]:
    """Parseia um <target> element."""
    name = _text(target_elem.find(TAG_NAME))
    gene_name = ""
    organism = "Humans"
    actions: list[str] = []

    polypeptide = target_elem.find(TAG_POLYPEPTIDE)
    if polypeptide is not None:
        gn = polypeptide.find(TAG_GENE_NAME)
        if gn is not None:
            gene_name = _text(gn)
        org = polypeptide.find(TAG_ORGANISM)
        if org is not None:
            organism = _text(org)

    actions_elem = target_elem.find(TAG_ACTIONS)
    if actions_elem is not None:
        for action in actions_elem.findall(TAG_ACTION):
            txt = _text(action)
            if txt:
                actions.append(txt)

    return {
        "name": name,
        "gene_name": gene_name,
        "actions": actions,
        "organism": organism,
    }


def _parse_enzyme(enzyme_elem: ET.Element) -> dict[str, Any]:
    """Parseia um <enzyme> element."""
    name = _text(enzyme_elem.find(TAG_NAME))
    gene_name = ""

    polypeptide = enzyme_elem.find(TAG_POLYPEPTIDE)
    if polypeptide is not None:
        gn = polypeptide.find(TAG_GENE_NAME)
        if gn is not None:
            gene_name = _text(gn)

    return {"name": name, "gene_name": gene_name}


def _parse_interaction(interaction_elem: ET.Element) -> dict[str, Any]:
    """Parseia um <drug-interaction> element."""
    partner_id = _text(interaction_elem.find(TAG_DRUGBANK_ID))
    partner_name = _text(interaction_elem.find(TAG_NAME))
    description = _text(interaction_elem.find(TAG_DESCRIPTION))

    return {
        "partner_id": partner_id,
        "partner_name": partner_name,
        "description": description,
    }


def iterparse_drugbank(xml_path: str) -> list[dict[str, Any]]:
    """Parseia DrugBank XML via iterparse → lista de dicts.

    Usa elem.clear() após processar cada <drug> para manter
    memory footprint baixo (~50MB para um XML de 175MB).

    Args:
        xml_path: Caminho para o arquivo DrugBank XML.

    Returns:
        Lista de dicts, cada um representando uma droga.
    """
    drugs: list[dict[str, Any]] = []
    count = 0

    for _event, elem in ET.iterparse(xml_path, events=("end",)):
        if elem.tag != TAG_DRUG:
            continue

        # Extrair drugbank_id (primeiro <drugbank-id> com primary=true ou o primeiro)
        drug_id = ""
        for db_id_elem in elem.findall(TAG_DRUGBANK_ID):
            db_id_text = _text(db_id_elem)
            if db_id_elem.get("primary") == "true" or not drug_id:
                drug_id = db_id_text

        if not drug_id:
            elem.clear()
            continue

        name = _text(elem.find(TAG_NAME))
        description = _text(elem.find(TAG_DESCRIPTION))
        mechanism = _text(elem.find(TAG_MECHANISM))
        pharmacodynamics = _text(elem.find(TAG_PHARMACODYNAMICS))

        # Categories
        categories: list[str] = []
        cats_elem = elem.find(TAG_CATEGORIES)
        if cats_elem is not None:
            for cat in cats_elem.findall(TAG_CATEGORY):
                cat_name = cat.find(TAG_NAME)  # category > category (mesma tag)
                # DrugBank format: <category><category>text</category>...</category>
                # Mas na prática: <categories><category><category>text</category></category>
                if cat_name is not None:
                    txt = _text(cat_name)
                    if txt:
                        categories.append(txt)

        # Synonyms
        synonyms: list[str] = []
        syns_elem = elem.find(TAG_SYNONYMS)
        if syns_elem is not None:
            for syn in syns_elem.findall(TAG_SYNONYM):
                txt = _text(syn)
                if txt:
                    synonyms.append(txt)

        # Targets
        targets: list[dict[str, Any]] = []
        targets_elem = elem.find(TAG_TARGETS)
        if targets_elem is not None:
            for target in targets_elem.findall(TAG_TARGET):
                targets.append(_parse_target(target))

        # Enzymes
        enzymes: list[dict[str, Any]] = []
        enzymes_elem = elem.find(TAG_ENZYMES)
        if enzymes_elem is not None:
            for enzyme in enzymes_elem.findall(TAG_ENZYME):
                enzymes.append(_parse_enzyme(enzyme))

        # Interactions
        interactions: list[dict[str, Any]] = []
        interactions_elem = elem.find(TAG_INTERACTIONS)
        if interactions_elem is not None:
            for interaction in interactions_elem.findall(TAG_INTERACTION):
                interactions.append(_parse_interaction(interaction))

        drugs.append(
            {
                "drugbank_id": drug_id,
                "name": name,
                "description": description,
                "mechanism_of_action": mechanism,
                "pharmacodynamics": pharmacodynamics,
                "categories": categories,
                "synonyms": synonyms,
                "targets": targets,
                "enzymes": enzymes,
                "interactions": interactions,
            }
        )

        count += 1
        if count % 1000 == 0:
            logger.info("DrugBank parse: %d drugs processed", count)

        elem.clear()

    logger.info("DrugBank parse complete: %d drugs total", count)
    return drugs
