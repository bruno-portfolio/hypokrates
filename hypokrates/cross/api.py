"""API pública de cruzamento de hipóteses — async-first."""

from __future__ import annotations

import asyncio
import logging
from datetime import UTC, datetime
from typing import TYPE_CHECKING

from hypokrates.cross.constants import DEFAULT_EMERGING_MAX, DEFAULT_NOVEL_MAX

if TYPE_CHECKING:
    from hypokrates.chembl.models import ChEMBLMechanism
    from hypokrates.dailymed.models import LabelEventsResult
    from hypokrates.drugbank.models import DrugBankInfo
    from hypokrates.opentargets.models import OTDrugSafety
from hypokrates.cross.models import HypothesisClassification, HypothesisResult
from hypokrates.evidence.builder import build_evidence
from hypokrates.evidence.models import Limitation
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
    "Signal detection via FAERS disproportionality (PRR/ROR/IC simplified) "
    "cross-referenced with PubMed literature count. "
    "Classification thresholds are heuristics — adjust for clinical domain."
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
    suspect_only: bool = False,
    _label_cache: LabelEventsResult | None = None,
    _drugbank_cache: DrugBankInfo | None = None,
    _ot_safety_cache: OTDrugSafety | None = None,
    _chembl_cache: ChEMBLMechanism | None = None,
) -> HypothesisResult:
    """Cruza sinal FAERS + literatura PubMed → classificação.

    Args:
        drug: Nome genérico do medicamento.
        event: Termo do evento adverso.
        novel_max: Até N papers = novel_hypothesis (default 0).
        emerging_max: Até N papers = emerging_signal (default 5). Acima = known.
        literature_limit: Máximo de artigos retornados na busca PubMed.
        use_mesh: Usar qualificadores MeSH na busca PubMed (mais preciso).
        use_cache: Se deve usar cache.
        check_label: Se deve verificar bula FDA via DailyMed.
        check_trials: Se deve buscar trials em ClinicalTrials.gov.
        check_drugbank: Se deve buscar mecanismo/interações no DrugBank.
        check_opentargets: Se deve buscar LRT score no OpenTargets.
        check_chembl: Se deve buscar mecanismo/targets via ChEMBL API.
        suspect_only: Se True, conta apenas reports onde a droga é suspect no FAERS.

    Thresholds são heurísticas — ajuste pro domínio clínico.

    Returns:
        HypothesisResult com classificação, sinal, literatura e evidência.
    """
    # 1+2. FAERS e PubMed são independentes — rodar em paralelo
    signal_result, pubmed_result = await asyncio.gather(
        stats_api.signal(drug, event, suspect_only=suspect_only, use_cache=use_cache),
        pubmed_api.search_papers(
            drug,
            event,
            limit=literature_limit,
            use_mesh=use_mesh,
            use_cache=use_cache,
        ),
    )

    # 3. Opcionais: DailyMed e Trials (paralelo se ambos)
    in_label: bool | None = None
    label_detail: str | None = None
    active_trials: int | None = None
    trials_detail: str | None = None

    if check_label and check_trials:
        from hypokrates.dailymed import api as dailymed_api
        from hypokrates.trials import api as trials_api

        label_result, trials_result = await asyncio.gather(
            dailymed_api.check_label(drug, event, use_cache=use_cache, _label_cache=_label_cache),
            trials_api.search_trials(drug, event, use_cache=use_cache),
        )
        in_label = label_result.in_label
        label_detail = _format_label_detail(label_result)
        active_trials = trials_result.active_count
        trials_detail = _format_trials_detail(trials_result)
    elif check_label:
        from hypokrates.dailymed import api as dailymed_api

        label_result = await dailymed_api.check_label(
            drug, event, use_cache=use_cache, _label_cache=_label_cache
        )
        in_label = label_result.in_label
        label_detail = _format_label_detail(label_result)
    elif check_trials:
        from hypokrates.trials import api as trials_api

        trials_result = await trials_api.search_trials(drug, event, use_cache=use_cache)
        active_trials = trials_result.active_count
        trials_detail = _format_trials_detail(trials_result)

    # 3b. DrugBank (drug-level, cached externally)
    mechanism: str | None = None
    interactions_list: list[str] = []
    enzymes_list: list[str] = []

    if check_drugbank:
        from hypokrates.drugbank import api as drugbank_api

        db_info: DrugBankInfo | None
        if _drugbank_cache is not None:
            db_info = _drugbank_cache
        else:
            db_info = await drugbank_api.drug_info(drug, _store=None)

        if db_info is not None:
            mechanism = db_info.mechanism_of_action or None
            interactions_list = [it.partner_name for it in db_info.interactions[:10]]
            enzymes_list = [e.gene_name for e in db_info.enzymes if e.gene_name]

    # 3c. OpenTargets (per-event LRT score)
    ot_llr: float | None = None

    if check_opentargets:
        from hypokrates.opentargets import api as opentargets_api

        ot_llr = await opentargets_api.drug_safety_score(
            drug, event, use_cache=use_cache, _safety_cache=_ot_safety_cache
        )

    # 3d. ChEMBL (mecanismo + targets, alternativa ao DrugBank sem download)
    if check_chembl and mechanism is None:
        from hypokrates.chembl import api as chembl_api

        if _chembl_cache is not None:
            chembl_mech = _chembl_cache
        else:
            chembl_mech = await chembl_api.drug_mechanism(drug, use_cache=use_cache)

        if chembl_mech.mechanism_of_action:
            mechanism = chembl_mech.mechanism_of_action
        if not enzymes_list and chembl_mech.targets:
            for t in chembl_mech.targets:
                enzymes_list.extend(g for g in t.gene_names if g not in enzymes_list)

    literature_count = pubmed_result.total_count
    articles = pubmed_result.articles

    classification = _classify(
        signal_detected=signal_result.signal_detected,
        literature_count=literature_count,
        novel_max=novel_max,
        emerging_max=emerging_max,
        in_label=in_label,
    )

    # 5. Gerar summary
    summary = _build_summary(drug, event, classification, literature_count, in_label=in_label)

    # 6. Gerar EvidenceBlock
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
    )


def _classify(
    *,
    signal_detected: bool,
    literature_count: int,
    novel_max: int,
    emerging_max: int,
    in_label: bool | None = None,
) -> HypothesisClassification:
    """Classifica hipótese com base em sinal, literatura e label."""
    if not signal_detected:
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
) -> str:
    """Gera resumo textual da classificação."""
    labels = {
        HypothesisClassification.NOVEL_HYPOTHESIS: "Novel hypothesis",
        HypothesisClassification.EMERGING_SIGNAL: "Emerging signal",
        HypothesisClassification.KNOWN_ASSOCIATION: "Known association",
        HypothesisClassification.NO_SIGNAL: "No signal",
    }
    label = labels[classification]

    parts = [
        f"{label}: {drug.upper()} + {event.upper()}.",
    ]

    if classification == HypothesisClassification.NO_SIGNAL:
        parts.append("No disproportionality signal detected in FAERS.")
    elif classification == HypothesisClassification.NOVEL_HYPOTHESIS:
        parts.append(
            f"FAERS signal detected but no published literature found "
            f"({literature_count} papers). Potential novel finding — requires validation."
        )
    elif classification == HypothesisClassification.EMERGING_SIGNAL:
        parts.append(
            f"FAERS signal detected with limited literature "
            f"({literature_count} papers). Emerging evidence — monitor closely."
        )
    else:
        parts.append(
            f"FAERS signal detected with substantial literature "
            f"({literature_count} papers). Well-documented association."
        )

    if in_label is True:
        parts.append("Event is listed in the FDA label.")
    elif in_label is False:
        parts.append("Event is NOT listed in the FDA label.")

    return " ".join(parts)


def _confidence_label(classification: HypothesisClassification) -> str:
    """Retorna label de confiança baseado na classificação."""
    labels = {
        HypothesisClassification.NOVEL_HYPOTHESIS: "low — no corroborating literature",
        HypothesisClassification.EMERGING_SIGNAL: "moderate — limited corroborating literature",
        HypothesisClassification.KNOWN_ASSOCIATION: "high — well-documented in literature",
        HypothesisClassification.NO_SIGNAL: "n/a — no signal detected",
    }
    return labels[classification]


def _format_label_detail(label_result: object) -> str:
    """Formata detalhe do label check."""
    matched = getattr(label_result, "matched_terms", [])
    if matched:
        return f"Matched: {', '.join(matched)}"
    return "Not found in label"


def _format_trials_detail(trials_result: object) -> str:
    """Formata detalhe dos trials."""
    total = getattr(trials_result, "total_count", 0)
    active = getattr(trials_result, "active_count", 0)
    return f"{total} trials found, {active} active"
