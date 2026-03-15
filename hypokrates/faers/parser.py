"""Parser de respostas OpenFDA -> domain models."""

from __future__ import annotations

import contextlib
import logging
from typing import Any

from hypokrates.faers.constants import OUTCOME_MAP, SEX_MAP
from hypokrates.faers.models import DrugCount, FAERSDrug, FAERSReaction, FAERSReport
from hypokrates.models import AdverseEvent, PatientProfile, Sex

logger = logging.getLogger(__name__)


def parse_reports(raw_results: list[dict[str, Any]]) -> list[FAERSReport]:
    """Converte lista de resultados OpenFDA em FAERSReport."""
    reports: list[FAERSReport] = []
    for raw in raw_results:
        try:
            reports.append(_parse_single_report(raw))
        except Exception:
            logger.warning(
                "Failed to parse report %s",
                raw.get("safetyreportid", "unknown"),
                exc_info=True,
            )
    return reports


def parse_count_results(raw_results: list[dict[str, Any]]) -> list[AdverseEvent]:
    """Converte resultados de count query em AdverseEvent."""
    events: list[AdverseEvent] = []
    for item in raw_results:
        term = item.get("term", "")
        count = item.get("count", 0)
        if term and isinstance(term, str):
            events.append(AdverseEvent(term=term, count=count))
    return events


def parse_drug_count_results(raw_results: list[dict[str, Any]]) -> list[DrugCount]:
    """Converte resultados de count query (por droga) em DrugCount."""
    drugs: list[DrugCount] = []
    for item in raw_results:
        term = item.get("term", "")
        count = item.get("count", 0)
        if term and isinstance(term, str):
            drugs.append(DrugCount(name=term, count=count))
    return drugs


def _parse_single_report(raw: dict[str, Any]) -> FAERSReport:
    """Parseia um report individual."""
    patient_raw = raw.get("patient", {})

    # Reações
    reactions = _parse_reactions(patient_raw.get("reaction") or [])

    # Drogas
    drugs = _parse_drugs(patient_raw.get("drug") or [])

    # Paciente
    patient = _parse_patient(patient_raw)

    # Serious reasons
    serious_reasons: list[str] = []
    if raw.get("seriousnessdeath") == "1":
        serious_reasons.append("death")
    if raw.get("seriousnesshospitalization") == "1":
        serious_reasons.append("hospitalization")
    if raw.get("seriousnesslifethreatening") == "1":
        serious_reasons.append("life_threatening")
    if raw.get("seriousnessdisabling") == "1":
        serious_reasons.append("disability")
    if raw.get("seriousnesscongenitalanomali") == "1":
        serious_reasons.append("congenital_anomaly")
    if raw.get("seriousnessother") == "1":
        serious_reasons.append("other")

    return FAERSReport(
        safety_report_id=str(raw.get("safetyreportid", "")),
        receive_date=raw.get("receivedate"),
        receipt_date=raw.get("receiptdate"),
        serious=raw.get("serious", "1") == "1",
        serious_reasons=serious_reasons,
        patient=patient,
        drugs=drugs,
        reactions=reactions,
        country=raw.get("occurcountry"),
        source_type=raw.get("primarysource", {}).get("qualification"),
    )


def _parse_reactions(raw_reactions: list[dict[str, Any]]) -> list[FAERSReaction]:
    """Parseia reações de um report."""
    reactions: list[FAERSReaction] = []
    for r in raw_reactions:
        term = r.get("reactionmeddrapt", "")
        if not term:
            continue
        outcome_code = str(r.get("reactionoutcome", ""))
        reactions.append(
            FAERSReaction(
                term=term,
                outcome=OUTCOME_MAP.get(outcome_code),
                version=r.get("reactionmeddraversionpt"),
            )
        )
    return reactions


def _parse_drugs(raw_drugs: list[dict[str, Any]]) -> list[FAERSDrug]:
    """Parseia drogas de um report."""
    drugs: list[FAERSDrug] = []
    for d in raw_drugs:
        openfda = d.get("openfda", {})
        names = openfda.get("generic_name", [])
        name = names[0] if names else d.get("medicinalproduct", "Unknown")
        drugs.append(
            FAERSDrug(
                name=name,
                role=d.get("drugcharacterization"),
                route=d.get("drugadministrationroute"),
                dose=d.get("drugdosagetext"),
                indication=d.get("drugindication"),
            )
        )
    return drugs


def _parse_patient(raw: dict[str, Any]) -> PatientProfile:
    """Parseia dados demográficos do paciente."""
    sex_code = str(raw.get("patientsex", "0"))
    sex_reverse = {v: k for k, v in SEX_MAP.items()}
    sex_str = sex_reverse.get(sex_code, "UNK")

    age: float | None = None
    age_raw = raw.get("patientonsetage")
    if age_raw is not None:
        with contextlib.suppress(ValueError, TypeError):
            age = float(age_raw)

    weight: float | None = None
    weight_raw = raw.get("patientweight")
    if weight_raw is not None:
        with contextlib.suppress(ValueError, TypeError):
            weight = float(weight_raw)

    return PatientProfile(
        age=age,
        age_unit=raw.get("patientonsetageunit"),
        sex=Sex(sex_str),
        weight=weight,
        weight_unit="kg" if weight is not None else None,
    )
