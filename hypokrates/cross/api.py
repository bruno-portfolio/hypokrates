from __future__ import annotations

import asyncio
import logging
import statistics
from datetime import UTC, datetime
from typing import TYPE_CHECKING

from hypokrates.cross.constants import (
    CO_ADMIN_COMPARE_TOP_N,
    COMPARE_RATIO_EQUAL_THRESHOLD,
    DEFAULT_COMPARE_CONCURRENCY,
    DEFAULT_COMPARE_TOP_N,
    DEFAULT_EMERGING_MAX,
    DEFAULT_NOVEL_MAX,
    OVERLAP_THRESHOLD,
    SPECIFICITY_RATIO_THRESHOLD,
)

if TYPE_CHECKING:
    from hypokrates.chembl.models import ChEMBLMechanism
    from hypokrates.dailymed.models import LabelEventsResult
    from hypokrates.drugbank.models import DrugBankInfo
    from hypokrates.faers.client import FAERSClient
    from hypokrates.faers.models import CoSuspectProfile
    from hypokrates.opentargets.models import OTDrugSafety
    from hypokrates.trials.models import TrialsResult
from hypokrates.cross.models import (
    CoAdminAnalysis,
    CompareResult,
    CompareSignalItem,
    CoSignalItem,
    HypothesisClassification,
    HypothesisResult,
)
from hypokrates.evidence.builder import build_evidence
from hypokrates.evidence.models import Limitation
from hypokrates.faers import api as faers_api
from hypokrates.models import MetaInfo
from hypokrates.pubmed import api as pubmed_api
from hypokrates.stats import api as stats_api

logger = logging.getLogger(__name__)

_CROSS_LIMITATIONS: list[Limitation] = [
    Limitation.VOLUNTARY_REPORTING,
    Limitation.NO_DENOMINATOR,
    Limitation.NO_CAUSATION,
]

_CROSS_METHODOLOGY = (
    "Signal detection via FAERS disproportionality (PRR/ROR/IC (BCPNN)) "
    "cross-referenced with PubMed literature count. "
    "Classification thresholds are heuristics — adjust for clinical domain."
)


async def coadmin_analysis(
    drug: str,
    event: str,
    profile: CoSuspectProfile,
    *,
    drug_prr: float = 0.0,
    top_n_compare: int = CO_ADMIN_COMPARE_TOP_N,
    suspect_only: bool = False,
    use_cache: bool = True,
) -> CoAdminAnalysis:
    """Analisa se o sinal é específico da droga ou artefato de co-administração.

    Layer 2: compara os top drugs para o evento (via drugs_by_event) com os
    co-suspects do Layer 1 (profile). Alta sobreposição + PRR similar entre
    co-drugs indica que o sinal é provavelmente confounding por co-administração.
    """
    dbe_result = await faers_api.drugs_by_event(
        event, suspect_only=suspect_only, limit=20, use_cache=use_cache
    )

    if not dbe_result.drugs or not profile.top_co_drugs:
        return CoAdminAnalysis(profile=profile, verdict="inconclusive")

    co_drug_names = {name for name, _ in profile.top_co_drugs}
    event_drug_names = {d.name.upper() for d in dbe_result.drugs}
    # Excluir a droga-índice
    event_drug_names.discard(drug.upper())

    if not event_drug_names:
        return CoAdminAnalysis(profile=profile, verdict="inconclusive")

    overlap = co_drug_names & event_drug_names
    overlap_ratio = len(overlap) / len(event_drug_names)

    if overlap_ratio < OVERLAP_THRESHOLD or not profile.co_admin_flag:
        return CoAdminAnalysis(
            profile=profile,
            overlap_ratio=round(overlap_ratio, 3),
            is_specific=True,
            verdict="specific",
        )

    co_drugs_to_compare = [name for name, _ in profile.top_co_drugs[:top_n_compare]]

    async def _safe_signal(co_drug: str) -> CoSignalItem | None:
        try:
            sig = await stats_api.signal(
                co_drug, event, suspect_only=suspect_only, use_cache=use_cache
            )
            return CoSignalItem(
                drug=co_drug,
                prr=round(sig.prr.value, 2),
                signal_detected=sig.signal_detected,
            )
        except Exception:
            logger.warning("coadmin signal failed: %s + %s", co_drug, event)
            return None

    co_results = await asyncio.gather(*[_safe_signal(d) for d in co_drugs_to_compare])
    co_signals = [r for r in co_results if r is not None]

    co_prrs = [cs.prr for cs in co_signals if cs.signal_detected and cs.prr > 0]
    specificity_ratio: float | None = None

    if co_prrs and drug_prr > 0:
        median_co = statistics.median(co_prrs)
        specificity_ratio = round(drug_prr / median_co, 2) if median_co > 0 else None

    if specificity_ratio is not None and specificity_ratio > SPECIFICITY_RATIO_THRESHOLD:
        verdict = "specific"
        is_specific = True
    elif specificity_ratio is not None and specificity_ratio <= SPECIFICITY_RATIO_THRESHOLD:
        verdict = "co_admin_artifact"
        is_specific = False
    else:
        verdict = "inconclusive"
        is_specific = True

    return CoAdminAnalysis(
        profile=profile,
        overlap_ratio=round(overlap_ratio, 3),
        specificity_ratio=specificity_ratio,
        is_specific=is_specific,
        co_signals=co_signals,
        verdict=verdict,
    )


async def hypothesis(
    drug: str,
    event: str,
    *,
    novel_max: int = DEFAULT_NOVEL_MAX,
    emerging_max: int = DEFAULT_EMERGING_MAX,
    literature_limit: int = 5,
    use_mesh: bool = False,
    use_cache: bool = True,
    check_label: bool = False,
    check_trials: bool = False,
    check_drugbank: bool = False,
    check_opentargets: bool = False,
    check_chembl: bool = False,
    check_coadmin: bool = False,
    check_onsides: bool = False,
    check_pharmgkb: bool = False,
    check_canada: bool = False,
    check_jader: bool = False,
    suspect_only: bool = False,
    use_bulk: bool | None = None,
    _label_cache: LabelEventsResult | None = None,
    _drugbank_cache: DrugBankInfo | None = None,
    _ot_safety_cache: OTDrugSafety | None = None,
    _chembl_cache: ChEMBLMechanism | None = None,
    _faers_client: FAERSClient | None = None,
    _drug_search: str | None = None,
    _drug_total: int | None = None,
    _n_total: int | None = None,
) -> HypothesisResult:
    """Cruza sinal FAERS + literatura PubMed → classificação.

    Thresholds são heurísticas — ajuste pro domínio clínico.
    """
    signal_result, pubmed_result = await asyncio.gather(
        stats_api.signal(
            drug,
            event,
            suspect_only=suspect_only,
            use_bulk=use_bulk,
            use_cache=use_cache,
            _client=_faers_client,
            _drug_search=_drug_search,
            _drug_total=_drug_total,
            _n_total=_n_total,
        ),
        pubmed_api.search_papers(
            drug,
            event,
            limit=literature_limit,
            use_mesh=use_mesh,
            use_cache=use_cache,
        ),
    )

    in_label: bool | None = None
    label_detail: str | None = None
    active_trials: int | None = None
    trials_detail: str | None = None

    label_cache: LabelEventsResult | None = _label_cache

    if check_label and check_trials:
        from hypokrates.dailymed import api as dailymed_api
        from hypokrates.trials import api as trials_api

        if label_cache is None:
            _label_task = asyncio.create_task(dailymed_api.label_events(drug, use_cache=use_cache))
            _trials_task = asyncio.create_task(
                trials_api.search_trials(drug, event, use_cache=use_cache)
            )
            try:
                label_cache = await _label_task
            except Exception:
                logger.warning("hypothesis %s + %s: label unavailable", drug, event)
            try:
                trials_result = await _trials_task
                active_trials = trials_result.active_count
                trials_detail = _format_trials_detail(trials_result)
            except Exception:
                logger.warning("hypothesis %s + %s: trials unavailable", drug, event)
        else:
            try:
                trials_result = await trials_api.search_trials(drug, event, use_cache=use_cache)
                active_trials = trials_result.active_count
                trials_detail = _format_trials_detail(trials_result)
            except Exception:
                logger.warning("hypothesis %s + %s: trials unavailable", drug, event)
    elif check_label:
        if label_cache is None:
            from hypokrates.dailymed import api as dailymed_api

            try:
                label_cache = await dailymed_api.label_events(drug, use_cache=use_cache)
            except Exception:
                logger.warning("hypothesis %s + %s: label unavailable", drug, event)
    elif check_trials:
        from hypokrates.trials import api as trials_api

        try:
            trials_result = await trials_api.search_trials(drug, event, use_cache=use_cache)
            active_trials = trials_result.active_count
            trials_detail = _format_trials_detail(trials_result)
        except Exception:
            logger.warning("hypothesis %s + %s: trials unavailable", drug, event)

    if label_cache is not None:
        from hypokrates.dailymed.parser import match_event_in_label as _match_label

        found, matched = _match_label(event, label_cache.events, label_cache.raw_text)
        in_label = found
        label_detail = f"Matched: {', '.join(matched)}" if matched else "Not found in label"

    mechanism: str | None = None
    interactions_list: list[str] = []
    enzymes_list: list[str] = []

    if check_drugbank:
        from hypokrates.drugbank import api as drugbank_api

        db_info: DrugBankInfo | None
        if _drugbank_cache is not None:
            db_info = _drugbank_cache
        else:
            try:
                db_info = await drugbank_api.drug_info(drug, _store=None)
            except Exception:
                logger.warning(
                    "hypothesis %s + %s: DrugBank unavailable, continuing without",
                    drug,
                    event,
                )
                db_info = None

        if db_info is not None:
            mechanism = db_info.mechanism_of_action or None
            interactions_list = [it.partner_name for it in db_info.interactions[:10]]
            enzymes_list = [e.gene_name for e in db_info.enzymes if e.gene_name]

    ot_llr: float | None = None

    if check_opentargets:
        from hypokrates.opentargets import api as opentargets_api

        try:
            ot_llr = await opentargets_api.drug_safety_score(
                drug, event, use_cache=use_cache, _safety_cache=_ot_safety_cache
            )
        except Exception:
            logger.warning("hypothesis %s + %s: OpenTargets unavailable", drug, event)

    if check_chembl and mechanism is None:
        from hypokrates.chembl import api as chembl_api

        try:
            if _chembl_cache is not None:
                chembl_mech = _chembl_cache
            else:
                chembl_mech = await chembl_api.drug_mechanism(drug, use_cache=use_cache)

            if chembl_mech.mechanism_of_action:
                mechanism = chembl_mech.mechanism_of_action
            if not enzymes_list and chembl_mech.targets:
                for t in chembl_mech.targets:
                    enzymes_list.extend(g for g in t.gene_names if g not in enzymes_list)
        except Exception:
            logger.warning("hypothesis %s + %s: ChEMBL unavailable", drug, event)

    onsides_sources: list[str] | None = None

    if check_onsides:
        from hypokrates.onsides import api as onsides_api_mod

        try:
            onsides_ev = await onsides_api_mod.onsides_check_event(drug, event)
            if onsides_ev is not None:
                onsides_sources = onsides_ev.sources
        except Exception:
            logger.warning("hypothesis %s + %s: OnSIDES unavailable", drug, event)

    canada_reports: int | None = None
    canada_signal_detected: bool | None = None
    canada_prr: float | None = None

    if check_canada:
        from hypokrates.canada import api as canada_api_mod

        try:
            canada_result = await canada_api_mod.canada_signal(
                drug, event, suspect_only=suspect_only
            )
            canada_reports = canada_result.drug_event_count
            canada_signal_detected = canada_result.signal_detected
            canada_prr = canada_result.prr
        except Exception:
            logger.warning("hypothesis %s + %s: Canada Vigilance unavailable", drug, event)

    jader_reports: int | None = None
    jader_signal_detected: bool | None = None
    jader_prr: float | None = None

    if check_jader:
        from hypokrates.jader import api as jader_api_mod

        try:
            jader_result = await jader_api_mod.jader_signal(drug, event, suspect_only=suspect_only)
            jader_reports = jader_result.drug_event_count
            jader_signal_detected = jader_result.signal_detected
            jader_prr = jader_result.prr
        except Exception:
            logger.warning("hypothesis %s + %s: JADER unavailable", drug, event)

    pharmacogenomics: list[str] = []

    if check_pharmgkb:
        from hypokrates.pharmgkb import api as pharmgkb_api_mod

        try:
            pgx_anns = await pharmgkb_api_mod.pgx_annotations(drug)
            seen_pgx: set[str] = set()
            for ann in pgx_anns[:8]:
                if ann.gene_symbol and ann.level_of_evidence:
                    cats = ", ".join(ann.annotation_types[:2]) if ann.annotation_types else ""
                    key = f"{ann.gene_symbol}|{ann.level_of_evidence}|{cats}"
                    if key in seen_pgx:
                        continue
                    seen_pgx.add(key)
                    summary = f"{ann.gene_symbol} (Level {ann.level_of_evidence})"
                    if cats:
                        summary += f" — {cats}"
                    pharmacogenomics.append(summary)
        except Exception:
            logger.warning("hypothesis %s + %s: PharmGKB unavailable", drug, event)

    literature_count = pubmed_result.total_count
    articles = pubmed_result.articles

    from hypokrates.pubmed.classify import classify_article

    for art in articles:
        if not art.category:
            art.category = classify_article(art)

    indication_confounding = False
    indication_source = ""
    try:
        from hypokrates.scan.indications import check_drug_indication

        ind_check = check_drug_indication(
            drug,
            event,
            indications_text=label_cache.indications_text if label_cache else "",
        )
        indication_confounding = ind_check.is_indication
        indication_source = ind_check.source
    except Exception:
        logger.debug("hypothesis %s + %s: indication detection unavailable", drug, event)

    classification = _classify(
        signal_detected=signal_result.signal_detected,
        literature_count=literature_count,
        novel_max=novel_max,
        emerging_max=emerging_max,
        in_label=in_label,
        prr=signal_result.prr.value,
        prr_ci_upper=signal_result.prr.ci_upper,
        drug_event_count=signal_result.table.a,
    )

    summary = _build_summary(
        drug,
        event,
        classification,
        literature_count,
        in_label=in_label,
        signal_detected=signal_result.signal_detected,
    )

    thresholds_used = {"novel_max": novel_max, "emerging_max": emerging_max}
    evidence = build_evidence(
        MetaInfo(
            source="FAERS+PubMed",
            query={"drug": drug, "event": event},
            total_results=signal_result.table.a,
            retrieved_at=datetime.now(UTC),
            disclaimer="Cross-reference of FAERS signal and PubMed literature. "
            "Classification is a heuristic — clinical validation required.",
        ),
        data={
            "signal_detected": signal_result.signal_detected,
            "faers_reports": signal_result.table.a,
            "literature_count": literature_count,
            "classification": classification.value,
            "thresholds": thresholds_used,
        },
        limitations=_CROSS_LIMITATIONS,
        methodology=_CROSS_METHODOLOGY,
        confidence=_confidence_label(classification),
    )

    # 3e. Co-administration analysis (Layer 1 sempre, Layer 2 se sinal detectado)
    coadmin_result: CoAdminAnalysis | None = None
    if check_coadmin:
        try:
            coadmin_profile = await faers_api.co_suspect_profile(
                drug,
                event,
                suspect_only=suspect_only,
                use_cache=use_cache,
                _client=_faers_client,
                _drug_search=_drug_search,
            )
            # Layer 2 roda quando há sinal OU co-admin flag alto
            if signal_result.signal_detected or coadmin_profile.co_admin_flag:
                coadmin_result = await coadmin_analysis(
                    drug,
                    event,
                    coadmin_profile,
                    drug_prr=signal_result.prr.value,
                    suspect_only=suspect_only,
                    use_cache=use_cache,
                )
            else:
                # Sem sinal FAERS e sem co-admin flag → Layer 1 only
                coadmin_result = CoAdminAnalysis(
                    profile=coadmin_profile,
                    verdict="no_signal",
                )
        except Exception:
            logger.warning("hypothesis %s + %s: coadmin analysis unavailable", drug, event)

    return HypothesisResult(
        drug=drug,
        event=event,
        classification=classification,
        signal=signal_result,
        literature_count=literature_count,
        articles=articles,
        evidence=evidence,
        summary=summary,
        thresholds_used=thresholds_used,
        in_label=in_label,
        label_detail=label_detail,
        active_trials=active_trials,
        trials_detail=trials_detail,
        mechanism=mechanism,
        interactions=interactions_list,
        enzymes=enzymes_list,
        ot_llr=ot_llr,
        coadmin=coadmin_result,
        indication_confounding=indication_confounding,
        indication_source=indication_source,
        onsides_sources=onsides_sources,
        pharmacogenomics=pharmacogenomics,
        canada_reports=canada_reports,
        canada_signal=canada_signal_detected,
        canada_prr=canada_prr,
        jader_reports=jader_reports,
        jader_signal=jader_signal_detected,
        jader_prr=jader_prr,
    )


def _classify(
    *,
    signal_detected: bool,
    literature_count: int,
    novel_max: int,
    emerging_max: int,
    in_label: bool | None = None,
    prr: float | None = None,
    prr_ci_upper: float | None = None,
    drug_event_count: int = 0,
) -> HypothesisClassification:
    if not signal_detected:
        # PRR < 1 com CI inteiro abaixo de 1 e dados existentes → protetor
        if (
            drug_event_count > 0
            and prr is not None
            and prr_ci_upper is not None
            and prr < 1.0
            and prr_ci_upper < 1.0
        ):
            return HypothesisClassification.PROTECTIVE_SIGNAL
        # Mesmo sem sinal FAERS, literatura substancial + bula = known
        if in_label is True and literature_count > emerging_max:
            return HypothesisClassification.KNOWN_ASSOCIATION
        # Literatura substancial sem bula → emerging (FAERS pode estar diluído)
        if literature_count > emerging_max:
            return HypothesisClassification.EMERGING_SIGNAL
        return HypothesisClassification.NO_SIGNAL

    if literature_count <= novel_max:
        # Refinamento: signal + in_label + 0 papers → EMERGING (não é novel se está na bula)
        if in_label is True:
            return HypothesisClassification.EMERGING_SIGNAL
        return HypothesisClassification.NOVEL_HYPOTHESIS

    if literature_count <= emerging_max:
        return HypothesisClassification.EMERGING_SIGNAL
    return HypothesisClassification.KNOWN_ASSOCIATION


def _build_summary(
    drug: str,
    event: str,
    classification: HypothesisClassification,
    literature_count: int,
    *,
    in_label: bool | None = None,
    signal_detected: bool = True,
) -> str:
    labels = {
        HypothesisClassification.NOVEL_HYPOTHESIS: "Novel hypothesis",
        HypothesisClassification.EMERGING_SIGNAL: "Emerging signal",
        HypothesisClassification.KNOWN_ASSOCIATION: "Known association",
        HypothesisClassification.NO_SIGNAL: "No signal",
        HypothesisClassification.PROTECTIVE_SIGNAL: "Protective association",
    }
    label = labels[classification]

    parts = [
        f"{label}: {drug.upper()} + {event.upper()}.",
    ]

    if classification == HypothesisClassification.PROTECTIVE_SIGNAL:
        parts.append(
            f"FAERS reporting rate is significantly BELOW expected (PRR < 1). "
            f"Literature count: {literature_count} papers. "
            f"Possible protective or preventive association."
        )
    elif classification == HypothesisClassification.NO_SIGNAL:
        parts.append("No disproportionality signal detected in FAERS.")
    elif classification == HypothesisClassification.NOVEL_HYPOTHESIS:
        parts.append(
            f"FAERS signal detected but no published literature found "
            f"({literature_count} papers). Potential novel finding — requires validation."
        )
    elif classification == HypothesisClassification.EMERGING_SIGNAL:
        if signal_detected:
            parts.append(
                f"FAERS signal detected with limited literature "
                f"({literature_count} papers). Emerging evidence — monitor closely."
            )
        else:
            parts.append(
                f"No FAERS disproportionality signal, but literature suggests "
                f"emerging evidence ({literature_count} papers). Monitor closely."
            )
    elif classification == HypothesisClassification.KNOWN_ASSOCIATION:
        if signal_detected:
            parts.append(
                f"FAERS signal detected with substantial literature "
                f"({literature_count} papers). Well-documented association."
            )
        else:
            parts.append(
                f"No FAERS signal, but well-documented in literature "
                f"({literature_count} papers) and FDA label."
            )

    if in_label is True:
        parts.append("Event is listed in the FDA label.")
    elif in_label is False:
        parts.append("Event is NOT listed in the FDA label.")

    return " ".join(parts)


def _confidence_label(classification: HypothesisClassification) -> str:
    labels = {
        HypothesisClassification.NOVEL_HYPOTHESIS: "low — no corroborating literature",
        HypothesisClassification.EMERGING_SIGNAL: "moderate — limited corroborating literature",
        HypothesisClassification.KNOWN_ASSOCIATION: "high — well-documented in literature",
        HypothesisClassification.NO_SIGNAL: "n/a — no signal detected",
        HypothesisClassification.PROTECTIVE_SIGNAL: (
            "moderate — PRR < 1, requires clinical validation"
        ),
    }
    return labels[classification]


def _format_trials_detail(trials_result: TrialsResult) -> str:
    return f"{trials_result.total_count} trials found, {trials_result.active_count} active"


async def compare_signals(
    drug: str,
    control: str,
    events: list[str] | None = None,
    *,
    target_event: str | None = None,
    top_n: int = DEFAULT_COMPARE_TOP_N,
    suspect_only: bool = False,
    use_cache: bool = True,
    annotate: bool = False,
) -> CompareResult:
    """Compara sinais de desproporcionalidade entre duas drogas.

    Para cada evento, roda signal() em ambas as drogas e calcula o ratio
    de PRR. Útil para separar sinal genuíno de confounding por indicação
    (ex: isotretinoin vs doxycycline na mesma população de acne).

    Args:
        drug: Nome da droga primária.
        control: Nome da droga controle (mesma classe/indicação).
        events: Lista de eventos para comparar. Se None, auto-detecta top N do drug.
        target_event: Evento a incluir forçadamente no auto-detect (ignorado se events != None).
        top_n: Número de top eventos a comparar quando auto-detectando.
        suspect_only: Se True, conta apenas reports onde a droga é suspect.
        use_cache: Se deve usar cache.
        annotate: Se True, enriquece com indication check e co-suspects.

    Returns:
        CompareResult com items ordenados por ratio descendente.
    """
    if events is None:
        faers_result = await faers_api.top_events(
            drug, suspect_only=suspect_only, limit=top_n * 2, use_cache=use_cache
        )
        raw_events = [ev.term for ev in faers_result.events]

        # Dedup por canonical MedDRA e filtrar operacionais
        from hypokrates.scan.constants import OPERATIONAL_MEDDRA_TERMS
        from hypokrates.vocab.meddra import canonical_term

        seen: set[str] = set()
        events = []
        for ev in raw_events:
            if ev.upper().strip() in OPERATIONAL_MEDDRA_TERMS:
                continue
            canon = canonical_term(ev)
            if canon not in seen:
                seen.add(canon)
                events.append(canon)
            if len(events) >= top_n:
                break

        if target_event is not None:
            target_canon = canonical_term(target_event)
            if target_canon not in seen:
                events.append(target_canon)

    if not events:
        return CompareResult(
            drug=drug,
            control=control,
            total_events=0,
            meta=MetaInfo(
                source="hypokrates/compare",
                query={"drug": drug, "control": control},
                total_results=0,
                retrieved_at=datetime.now(UTC),
            ),
        )

    # Pre-fetch indications para annotation (0 custo extra se cacheado)
    drug_indications_text = ""
    control_indications_text = ""
    if annotate:
        from hypokrates.dailymed import api as dailymed_api

        try:
            drug_label, ctrl_label = await asyncio.gather(
                dailymed_api.label_events(drug, use_cache=use_cache),
                dailymed_api.label_events(control, use_cache=use_cache),
            )
            drug_indications_text = drug_label.indications_text
            control_indications_text = ctrl_label.indications_text
        except Exception:
            logger.debug("compare_signals: indications pre-fetch failed")

    semaphore = asyncio.Semaphore(DEFAULT_COMPARE_CONCURRENCY)

    async def _compare_one(
        event_term: str,
    ) -> CompareSignalItem | None:
        async with semaphore:
            try:
                drug_sig, ctrl_sig = await asyncio.gather(
                    stats_api.signal(
                        drug,
                        event_term,
                        suspect_only=suspect_only,
                        use_cache=use_cache,
                    ),
                    stats_api.signal(
                        control,
                        event_term,
                        suspect_only=suspect_only,
                        use_cache=use_cache,
                    ),
                )
            except Exception:
                logger.warning("Compare %s vs %s: %s FAILED", drug, control, event_term)
                return None

            d_prr = drug_sig.prr.value
            c_prr = ctrl_sig.prr.value
            d_ebgm = drug_sig.ebgm.value
            c_ebgm = ctrl_sig.ebgm.value

            if c_prr > 0:
                ratio = d_prr / c_prr
            elif d_prr > 0:
                ratio = float("inf")
            else:
                ratio = 0.0

            if ratio == float("inf") or ratio > 1.0 + COMPARE_RATIO_EQUAL_THRESHOLD:
                stronger = "drug"
            elif ratio < 1.0 - COMPARE_RATIO_EQUAL_THRESHOLD:
                stronger = "control"
            else:
                stronger = "equal"

            # Annotations (opt-in)
            drug_indication = False
            control_indication = False
            top_co_suspects: list[str] = []
            if annotate:
                try:
                    from hypokrates.scan.indications import check_drug_indication

                    d_ind = check_drug_indication(
                        drug, event_term, indications_text=drug_indications_text
                    )
                    drug_indication = d_ind.is_indication
                    c_ind = check_drug_indication(
                        control, event_term, indications_text=control_indications_text
                    )
                    control_indication = c_ind.is_indication
                except Exception:
                    pass
                try:
                    dbe = await faers_api.drugs_by_event(
                        event_term, suspect_only=suspect_only, limit=5, use_cache=use_cache
                    )
                    exclude = {drug.upper(), control.upper()}
                    top_co_suspects = [d.name for d in dbe.drugs if d.name.upper() not in exclude][
                        :3
                    ]
                except Exception:
                    pass

            return CompareSignalItem(
                event=event_term,
                drug_prr=round(d_prr, 2),
                control_prr=round(c_prr, 2),
                drug_ebgm=round(d_ebgm, 2),
                control_ebgm=round(c_ebgm, 2),
                drug_detected=drug_sig.signal_detected,
                control_detected=ctrl_sig.signal_detected,
                ratio=round(ratio, 2) if ratio != float("inf") else ratio,
                stronger=stronger,
                drug_indication=drug_indication,
                control_indication=control_indication,
                top_co_suspects=top_co_suspects,
            )

    tasks = [_compare_one(ev) for ev in events]
    results = await asyncio.gather(*tasks)

    items: list[CompareSignalItem] = [r for r in results if r is not None]
    items.sort(key=lambda x: x.ratio if x.ratio != float("inf") else 1e9, reverse=True)

    drug_unique = sum(1 for it in items if it.drug_detected and not it.control_detected)
    control_unique = sum(1 for it in items if it.control_detected and not it.drug_detected)
    both = sum(1 for it in items if it.drug_detected and it.control_detected)

    return CompareResult(
        drug=drug,
        control=control,
        items=items,
        drug_unique_signals=drug_unique,
        control_unique_signals=control_unique,
        both_detected=both,
        total_events=len(items),
        meta=MetaInfo(
            source="hypokrates/compare",
            query={"drug": drug, "control": control, "events_count": len(items)},
            total_results=len(items),
            retrieved_at=datetime.now(UTC),
            disclaimer="Intra-class comparison of FAERS disproportionality. "
            "PRR ratio > 1 means drug has stronger signal than control. "
            "Does not imply causation — confounding by indication may persist.",
        ),
    )
