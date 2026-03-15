"""Parsers para respostas ClinicalTrials.gov v2 API."""

from __future__ import annotations

import logging
from typing import Any

from hypokrates.trials.constants import ACTIVE_STATUSES
from hypokrates.trials.models import ClinicalTrial

logger = logging.getLogger(__name__)


def parse_studies(data: dict[str, Any]) -> tuple[int, list[ClinicalTrial]]:
    """Parseia resposta de busca de estudos.

    Args:
        data: JSON response de /studies.

    Returns:
        Tupla (total_count, lista de ClinicalTrial).
    """
    total_count: int = data.get("totalCount", 0)
    studies: list[dict[str, Any]] = data.get("studies", [])

    trials: list[ClinicalTrial] = []
    for study in studies:
        trial = build_trial(study)
        if trial is not None:
            trials.append(trial)

    # Fallback: se totalCount=0 mas temos studies, usar len(studies)
    if total_count == 0 and trials:
        total_count = len(trials)

    return total_count, trials


def build_trial(study: dict[str, Any]) -> ClinicalTrial | None:
    """Constrói ClinicalTrial a partir de um estudo da API v2.

    Args:
        study: Objeto de estudo do JSON response.

    Returns:
        ClinicalTrial ou None se dados insuficientes.
    """
    protocol = study.get("protocolSection", {})
    id_module = protocol.get("identificationModule", {})
    status_module = protocol.get("statusModule", {})
    design_module = protocol.get("designModule", {})
    conditions_module = protocol.get("conditionsModule", {})
    interventions_module = protocol.get("armsInterventionsModule", {})

    nct_id = id_module.get("nctId", "")
    if not nct_id:
        return None

    title = id_module.get("briefTitle", "")
    status = status_module.get("overallStatus", "")

    # Phase
    phases = design_module.get("phases", [])
    phase = phases[0] if phases else ""

    # Start date
    start_info = status_module.get("startDateStruct", {})
    start_date = start_info.get("date")

    # Conditions
    conditions: list[str] = conditions_module.get("conditions", [])

    # Interventions
    interventions_list: list[str] = []
    for interv in interventions_module.get("interventions", []):
        name = interv.get("name", "")
        if name:
            interventions_list.append(name)

    return ClinicalTrial(
        nct_id=nct_id,
        title=title,
        status=status,
        phase=phase,
        start_date=start_date,
        conditions=conditions,
        interventions=interventions_list,
    )


def count_active(trials: list[ClinicalTrial]) -> int:
    """Conta trials com status ativo."""
    return sum(1 for t in trials if t.status in ACTIVE_STATUSES)
