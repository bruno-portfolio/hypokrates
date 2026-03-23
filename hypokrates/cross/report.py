"""Relatório completo: orquestra investigate + scan + compare."""

from __future__ import annotations

import asyncio
import logging
from datetime import UTC, datetime

from pydantic import BaseModel

from hypokrates.cross.api import compare_signals
from hypokrates.cross.investigate import investigate
from hypokrates.cross.models import (
    CompareResult,
    InvestigationResult,
    SignalStrength,
    SynthesisDirection,
)
from hypokrates.models import MetaInfo
from hypokrates.scan.api import scan_drug
from hypokrates.scan.models import ScanResult  # noqa: TC001 — Pydantic needs at runtime

logger = logging.getLogger(__name__)


class FullReportResult(BaseModel):
    """Resultado do relatório completo."""

    drug: str
    event: str
    investigation: InvestigationResult
    scan: ScanResult | None = None
    comparison: CompareResult | None = None
    synthesis: SynthesisDirection
    meta: MetaInfo


# --- Synthesis helpers (pure functions) ---


def _compute_signal_strength(investigation: InvestigationResult) -> SignalStrength:
    hyp = investigation.hypothesis
    if not hyp.signal.signal_detected:
        return SignalStrength.NONE
    prr = hyp.signal.prr.value
    significant = hyp.signal.prr.significant
    if prr >= 5.0 and significant:
        return SignalStrength.STRONG
    if prr >= 2.0 and significant:
        return SignalStrength.MODERATE
    return SignalStrength.WEAK


def _compute_replication(investigation: InvestigationResult) -> str:
    country = investigation.country_strata
    if not country:
        return "0/0"
    detecting = sum(1 for s in country if s.signal_detected)
    return f"{detecting}/{len(country)}"


def _compute_label_status(investigation: InvestigationResult) -> str:
    hyp = investigation.hypothesis
    parts: list[str] = []
    if hyp.in_label is True:
        parts.append("IN_LABEL")
    elif hyp.in_label is False:
        parts.append("NOT_IN_LABEL")
    else:
        parts.append("UNKNOWN")
    if hyp.onsides_sources:
        parts.append(f"OnSIDES:{len(hyp.onsides_sources)}/4")
    if hyp.active_trials is not None and hyp.active_trials > 0:
        parts.append(f"{hyp.active_trials} active trials")
    return ", ".join(parts)


def _compute_class_effect(
    event: str,
    comparison: CompareResult | None,
    control: str,
) -> str:
    if not control or comparison is None:
        return "NOT_TESTED"
    event_upper = event.upper()
    for item in comparison.items:
        if item.event.upper() == event_upper:
            if item.control_prr <= 0:
                return f"NO (control PRR=0 for {event})"
            ratio = item.drug_prr / item.control_prr
            if 0.5 <= ratio <= 2.0:
                return (
                    f"YES (drug PRR={item.drug_prr:.2f}, "
                    f"control PRR={item.control_prr:.2f}, "
                    f"ratio={ratio:.2f})"
                )
            return (
                f"NO (drug PRR={item.drug_prr:.2f}, "
                f"control PRR={item.control_prr:.2f}, "
                f"ratio={ratio:.2f})"
            )
    return "NOT_IN_TOP_COMPARED"


def _compute_demographic_bias(caveats: list[str]) -> str:
    from hypokrates.cross.constants import CAVEAT_PREFIX_AGE, CAVEAT_PREFIX_SEX

    for c in caveats:
        if CAVEAT_PREFIX_SEX in c or CAVEAT_PREFIX_AGE in c:
            detail = c.split(":")[0] if ":" in c else c
            return f"LIKELY ({detail})"
    return "UNLIKELY"


def _compute_mechanism(investigation: InvestigationResult) -> str:
    hyp = investigation.hypothesis
    if hyp.mechanism:
        return f"KNOWN ({hyp.mechanism[:120]})"
    return "UNKNOWN"


def _compute_top_events_context(
    event: str,
    scan: ScanResult | None,
) -> str:
    if scan is None:
        return "unavailable"
    event_upper = event.upper()
    for i, item in enumerate(scan.items):
        if item.event.upper() == event_upper:
            return f"ranks #{i + 1} of {len(scan.items)}, score={item.score:.1f}"
    return f"not in top {len(scan.items)}"


def _build_synthesis(
    investigation: InvestigationResult,
    scan: ScanResult | None,
    comparison: CompareResult | None,
    control: str,
    event: str,
) -> SynthesisDirection:
    hyp = investigation.hypothesis
    caveats = investigation.caveats
    return SynthesisDirection(
        signal_strength=_compute_signal_strength(investigation),
        classification=hyp.classification,
        reports=hyp.signal.table.a,
        caveats_triggered=len(caveats),
        caveats_list=caveats,
        replication_ratio=_compute_replication(investigation),
        label_status=_compute_label_status(investigation),
        literature_count=hyp.literature_count,
        class_effect=_compute_class_effect(event, comparison, control),
        demographic_bias=_compute_demographic_bias(caveats),
        indication_confounding=hyp.indication_confounding,
        coadmin_confounding=(
            hyp.coadmin is not None
            and hyp.coadmin.profile.co_admin_flag
            and hyp.coadmin.verdict != "specific"
        ),
        mechanism_plausibility=_compute_mechanism(investigation),
        top_events_context=_compute_top_events_context(event, scan),
    )


# --- Main orchestrator ---


async def full_report_analysis(
    drug: str,
    event: str,
    *,
    control: str = "",
    suspect_only: bool = False,
) -> FullReportResult:
    """Orquestra investigate + scan_drug + compare_signals em paralelo."""
    start = datetime.now(UTC)

    inv_coro = investigate(drug, event, suspect_only=suspect_only, literature_limit=20)
    scan_coro = scan_drug(drug, top_n=5, suspect_only=suspect_only)

    comp_result: CompareResult | None = None

    if control:
        inv_raw, scan_raw, comp_raw = await asyncio.gather(
            inv_coro,
            scan_coro,
            compare_signals(
                drug, control, suspect_only=suspect_only, annotate=True, target_event=event
            ),
            return_exceptions=True,
        )
        if isinstance(comp_raw, BaseException):
            logger.warning("full_report %s+%s: compare failed: %s", drug, event, comp_raw)
        else:
            comp_result = comp_raw
    else:
        inv_raw, scan_raw = await asyncio.gather(inv_coro, scan_coro, return_exceptions=True)

    # investigate é obrigatório
    if isinstance(inv_raw, BaseException):
        raise inv_raw
    inv_result: InvestigationResult = inv_raw

    scan_result: ScanResult | None = None
    if isinstance(scan_raw, BaseException):
        logger.warning("full_report %s+%s: scan failed: %s", drug, event, scan_raw)
    else:
        scan_result = scan_raw

    synthesis = _build_synthesis(inv_result, scan_result, comp_result, control, event)

    elapsed = (datetime.now(UTC) - start).total_seconds()

    return FullReportResult(
        drug=drug,
        event=event,
        investigation=inv_result,
        scan=scan_result,
        comparison=comp_result,
        synthesis=synthesis,
        meta=MetaInfo(
            source="hypokrates/full_report",
            query={"drug": drug, "event": event, "control": control or None},
            total_results=inv_result.hypothesis.signal.table.a,
            retrieved_at=datetime.now(UTC),
            disclaimer=(
                "Full pharmacovigilance report combining investigation, "
                "drug scan, and class comparison. Synthesis direction "
                "is a heuristic — clinical validation required."
            ),
            fetch_duration_ms=int(elapsed * 1000),
        ),
    )
