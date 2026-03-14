"""API pública do módulo ChEMBL — async-first."""

from __future__ import annotations

import logging
from datetime import UTC, datetime

from hypokrates.chembl.client import ChEMBLClient
from hypokrates.chembl.constants import (
    MECHANISM_ENDPOINT,
    METABOLISM_ENDPOINT,
    MOLECULE_SEARCH_ENDPOINT,
    TARGET_ENDPOINT,
)
from hypokrates.chembl.models import ChEMBLMechanism, ChEMBLMetabolism
from hypokrates.chembl.parser import (
    parse_mechanisms,
    parse_metabolism,
    parse_molecule_name,
    parse_molecule_search,
    parse_target,
)
from hypokrates.models import MetaInfo

logger = logging.getLogger(__name__)


async def _resolve_chembl_id(
    client: ChEMBLClient,
    drug_name: str,
    *,
    use_cache: bool = True,
) -> tuple[str, str]:
    """Resolve drug name → ChEMBL ID + preferred name.

    Returns:
        Tuple (chembl_id, pref_name). Ambos vazios se não encontrado.
    """
    data = await client.get(
        MOLECULE_SEARCH_ENDPOINT,
        {"q": drug_name, "limit": 1},
        use_cache=use_cache,
    )
    chembl_id = parse_molecule_search(data) or ""
    pref_name = parse_molecule_name(data) or drug_name
    return chembl_id, pref_name


async def drug_mechanism(
    drug_name: str,
    *,
    use_cache: bool = True,
    _chembl_id: str | None = None,
) -> ChEMBLMechanism:
    """Busca mecanismo de ação e targets de uma droga no ChEMBL.

    Args:
        drug_name: Nome da droga.
        use_cache: Se deve usar cache.
        _chembl_id: ChEMBL ID pré-resolvido (para evitar re-fetch).

    Returns:
        ChEMBLMechanism com mechanism_of_action, action_type, targets.
    """
    client = ChEMBLClient()
    try:
        # 1. Resolver nome → ChEMBL ID
        if _chembl_id:
            chembl_id = _chembl_id
            pref_name = drug_name
        else:
            chembl_id, pref_name = await _resolve_chembl_id(client, drug_name, use_cache=use_cache)

        if not chembl_id:
            logger.info("ChEMBL: drug '%s' not found", drug_name)
            return ChEMBLMechanism(
                chembl_id="",
                drug_name=drug_name,
                meta=_meta(drug_name, chembl_id),
            )

        # 2. Buscar mecanismos
        mech_data = await client.get(
            MECHANISM_ENDPOINT,
            {"molecule_chembl_id": chembl_id},
            use_cache=use_cache,
        )
        mechanisms = parse_mechanisms(mech_data)

        if not mechanisms:
            return ChEMBLMechanism(
                chembl_id=chembl_id,
                drug_name=pref_name,
                meta=_meta(drug_name, chembl_id),
            )

        # Usar o primeiro mecanismo (geralmente o principal / max_phase mais alto)
        best = max(mechanisms, key=lambda m: m.get("max_phase", 0))
        moa = best.get("mechanism_of_action", "")
        action = best.get("action_type", "")
        max_phase = best.get("max_phase", 0)
        target_chembl_id = best.get("target_chembl_id", "")

        # 3. Resolver target → gene names
        targets = []
        if target_chembl_id:
            target_endpoint = f"{TARGET_ENDPOINT}/{target_chembl_id}.json"
            try:
                target_data = await client.get(target_endpoint, use_cache=use_cache)
                target = parse_target(target_data)
                targets.append(target)
            except Exception:
                logger.warning("ChEMBL: failed to fetch target %s", target_chembl_id)

        return ChEMBLMechanism(
            chembl_id=chembl_id,
            drug_name=pref_name,
            mechanism_of_action=moa,
            action_type=action,
            targets=targets,
            max_phase=max_phase if isinstance(max_phase, int) else 0,
            meta=_meta(drug_name, chembl_id),
        )
    finally:
        await client.close()


async def drug_targets(
    drug_name: str,
    *,
    use_cache: bool = True,
    _chembl_id: str | None = None,
) -> list[str]:
    """Retorna gene names dos targets de uma droga.

    Convenience wrapper sobre drug_mechanism().

    Args:
        drug_name: Nome da droga.
        use_cache: Se deve usar cache.
        _chembl_id: ChEMBL ID pré-resolvido.

    Returns:
        Lista de gene names (e.g., ["GABRA1", "GABRB2"]).
    """
    mech = await drug_mechanism(drug_name, use_cache=use_cache, _chembl_id=_chembl_id)
    genes: list[str] = []
    for target in mech.targets:
        genes.extend(target.gene_names)
    return genes


async def drug_metabolism(
    drug_name: str,
    *,
    use_cache: bool = True,
    _chembl_id: str | None = None,
) -> ChEMBLMetabolism:
    """Busca vias metabólicas de uma droga no ChEMBL.

    Args:
        drug_name: Nome da droga.
        use_cache: Se deve usar cache.
        _chembl_id: ChEMBL ID pré-resolvido.

    Returns:
        ChEMBLMetabolism com enzimas e conversões.
    """
    client = ChEMBLClient()
    try:
        if _chembl_id:
            chembl_id = _chembl_id
            pref_name = drug_name
        else:
            chembl_id, pref_name = await _resolve_chembl_id(client, drug_name, use_cache=use_cache)

        if not chembl_id:
            return ChEMBLMetabolism(
                chembl_id="",
                drug_name=drug_name,
                meta=_meta(drug_name, ""),
            )

        met_data = await client.get(
            METABOLISM_ENDPOINT,
            {"molecule_chembl_id": chembl_id},
            use_cache=use_cache,
        )
        pathways = parse_metabolism(met_data)

        return ChEMBLMetabolism(
            chembl_id=chembl_id,
            drug_name=pref_name,
            pathways=pathways,
            meta=_meta(drug_name, chembl_id),
        )
    finally:
        await client.close()


def _meta(drug_name: str, chembl_id: str) -> MetaInfo:
    """Cria MetaInfo padrão para respostas ChEMBL."""
    return MetaInfo(
        source="ChEMBL",
        query={"drug": drug_name, "chembl_id": chembl_id},
        total_results=1 if chembl_id else 0,
        retrieved_at=datetime.now(UTC),
        disclaimer="Data from ChEMBL (EMBL-EBI). "
        "Mechanism and metabolism data — clinical validation required.",
    )
