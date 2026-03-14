"""Parser de respostas da API ChEMBL."""

from __future__ import annotations

from typing import Any

from hypokrates.chembl.models import ChEMBLTarget, MetabolismPathway


def parse_molecule_search(data: dict[str, Any]) -> str | None:
    """Extrai ChEMBL ID da resposta de search.

    Returns:
        ChEMBL ID ou None se não encontrado.
    """
    molecules = data.get("molecules", [])
    if not molecules:
        return None
    return str(molecules[0].get("molecule_chembl_id", ""))


def parse_molecule_name(data: dict[str, Any]) -> str:
    """Extrai nome preferencial de uma molécula."""
    molecules = data.get("molecules", [])
    if not molecules:
        return ""
    return str(molecules[0].get("pref_name", "") or "")


def parse_mechanisms(data: dict[str, Any]) -> list[dict[str, Any]]:
    """Extrai mecanismos de ação da resposta.

    Returns:
        Lista de dicts com mechanism_of_action, action_type, target_chembl_id, max_phase.
    """
    mechanisms = data.get("mechanisms", [])
    results: list[dict[str, Any]] = []
    for mech in mechanisms:
        results.append(
            {
                "mechanism_of_action": mech.get("mechanism_of_action", ""),
                "action_type": mech.get("action_type", ""),
                "target_chembl_id": mech.get("target_chembl_id", ""),
                "max_phase": mech.get("max_phase", 0),
            }
        )
    return results


def parse_target(data: dict[str, Any]) -> ChEMBLTarget:
    """Parseia resposta de target → ChEMBLTarget com gene names.

    A resposta tem target_components com component_description e target_component_synonyms.
    Gene names estão em target_components[].gene_name (campo direto, não synonym).
    """
    target_id = str(data.get("target_chembl_id", ""))
    name = str(data.get("pref_name", "") or "")
    organism = str(data.get("organism", "Homo sapiens") or "Homo sapiens")

    gene_names: list[str] = []
    components = data.get("target_components", [])
    if components:
        for comp in components:
            # target_component_synonyms pode ter gene symbols
            # mas o campo mais confiável é component_id → accession mapping
            synonyms = comp.get("target_component_synonyms", [])
            for syn in synonyms:
                if syn.get("syn_type") == "GENE_SYMBOL":
                    val = syn.get("component_synonym", "")
                    if val and val not in gene_names:
                        gene_names.append(val)

    return ChEMBLTarget(
        target_chembl_id=target_id,
        name=name,
        gene_names=gene_names,
        organism=organism,
    )


def parse_metabolism(
    data: dict[str, Any],
    *,
    chembl_id: str = "",
) -> list[MetabolismPathway]:
    """Extrai vias metabólicas da resposta.

    Args:
        data: JSON response do ChEMBL.
        chembl_id: ChEMBL ID para filtrar (safety net — a API pode
            ignorar o filtro e retornar dados de outras drogas).

    Returns:
        Lista de MetabolismPathway.
    """
    metabolisms = data.get("metabolisms", [])
    pathways: list[MetabolismPathway] = []
    for met in metabolisms:
        # Filtrar client-side: só aceitar registros da droga correta
        if chembl_id:
            drug_id = met.get("drug_chembl_id", "")
            substrate_id = met.get("substrate_chembl_id", "")
            if drug_id != chembl_id and substrate_id != chembl_id:
                continue
        pathways.append(
            MetabolismPathway(
                enzyme_name=met.get("enzyme_name", "") or "",
                substrate_name=met.get("substrate_name", "") or "",
                metabolite_name=met.get("metabolite_name", "") or "",
                conversion=met.get("met_conversion", "") or "",
                organism=met.get("organism", "Homo sapiens") or "Homo sapiens",
            )
        )
    return pathways
