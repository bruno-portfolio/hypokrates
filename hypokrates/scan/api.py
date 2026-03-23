"""API pública do módulo scan — async-first."""

from __future__ import annotations

import asyncio
import logging
from datetime import UTC, datetime
from typing import TYPE_CHECKING

from hypokrates.cross import api as cross_api
from hypokrates.cross.models import HypothesisClassification, HypothesisResult
from hypokrates.exceptions import HypokratesError
from hypokrates.faers import api as faers_api
from hypokrates.faers.client import FAERSClient
from hypokrates.faers.constants import (
    DRUG_CHARACTERIZATION_FIELD,
    DRUG_CHARACTERIZATION_SUSPECT,
)
from hypokrates.models import AdverseEvent, MetaInfo
from hypokrates.scan.clusters import get_cluster
from hypokrates.scan.constants import (
    CLASSIFICATION_WEIGHTS,
    CO_ADMIN_MULTIPLIER,
    DEFAULT_CONCURRENCY,
    DEFAULT_TOP_N,
    DIRECTION_STRENGTHENS_THRESHOLD,
    DIRECTION_WEAKENS_THRESHOLD,
    INDICATION_MULTIPLIER,
    LABEL_IN_MULTIPLIER,
    LABEL_NOT_IN_MULTIPLIER,
    OPERATIONAL_MEDDRA_TERMS,
    OVERFETCH_MULTIPLIER,
    PRR_DISCLAIMER,
    SCAN_METHODOLOGY,
    VOLUME_ANOMALY_THRESHOLD,
)
from hypokrates.scan.indications import is_indication_term
from hypokrates.scan.models import ScanItem, ScanResult

if TYPE_CHECKING:
    from collections.abc import Callable

    from hypokrates.chembl.models import ChEMBLMechanism
    from hypokrates.dailymed.models import LabelEventsResult
    from hypokrates.drugbank.models import DrugBankInfo
    from hypokrates.faers_bulk.constants import RoleCodFilter
    from hypokrates.opentargets.models import OTDrugSafety

logger = logging.getLogger(__name__)


async def scan_drug(
    drug: str,
    *,
    top_n: int = DEFAULT_TOP_N,
    concurrency: int = DEFAULT_CONCURRENCY,
    include_no_signal: bool = False,
    use_cache: bool = True,
    check_labels: bool = False,
    check_trials: bool = False,
    check_drugbank: bool = False,
    check_opentargets: bool = False,
    check_chembl: bool = False,
    group_events: bool = True,
    filter_operational: bool = True,
    suspect_only: bool = False,
    primary_suspect_only: bool = False,
    check_coadmin: bool = False,
    check_onsides: bool = False,
    check_pharmgkb: bool = False,
    check_canada: bool = False,
    check_jader: bool = False,
    check_direction: bool = False,
    use_bulk: bool | None = None,
    on_progress: Callable[[int, int, str], None] | None = None,
) -> ScanResult:
    """Escaneia os top eventos adversos de uma droga e gera hipóteses.

    Executa hypothesis() para cada um dos top N eventos adversos no FAERS.
    Cada hipótese envolve ~5 requests HTTP (4 FAERS + 1 PubMed).

    Tempo estimado:
    - Sem API key FAERS (40/min): ~2-3 minutos para 20 eventos
    - Com API key FAERS (240/min): ~30-60 segundos para 20 eventos

    Args:
        drug: Nome genérico do medicamento.
        top_n: Número de top eventos para escanear.
        concurrency: Máximo de hipóteses simultâneas.
        include_no_signal: Se True, inclui eventos sem sinal no resultado.
        use_cache: Se deve usar cache.
        check_labels: Se deve verificar bula FDA via DailyMed para cada evento.
        check_trials: Se deve buscar trials em ClinicalTrials.gov para cada evento.
        check_drugbank: Se deve buscar mecanismo/interações no DrugBank.
        check_opentargets: Se deve buscar LRT score no OpenTargets.
        check_chembl: Se deve buscar mecanismo/targets via ChEMBL API.
        group_events: Se deve agrupar termos MedDRA sinônimos.
        filter_operational: Se deve filtrar termos MedDRA operacionais/regulatórios.
        suspect_only: Se True, conta apenas reports onde a droga é suspect no FAERS.
        primary_suspect_only: Se True + bulk, usa PS_ONLY (apenas Primary Suspect).
            Requer bulk; sem bulk, faz fallback para suspect_only com warning.
        check_coadmin: Se True, analisa confounding por co-administração (Layer 1).
        check_onsides: Se True, verifica bulas internacionais via OnSIDES (US/EU/UK/JP).
        check_pharmgkb: Se True, busca farmacogenômica via PharmGKB.
        check_canada: Se True, verifica sinal no Canada Vigilance.
        check_jader: Se True, verifica sinal no JADER (Japão).
        check_direction: Se True + bulk, compara PRR base vs PS-only para cada sinal.
            "strengthens" se PS PRR > 1.2x base, "weakens" se < 0.8x.
        use_bulk: None=auto-detect, True=forçar bulk, False=forçar API.
        on_progress: Callback opcional (completed, total, event_term).

    Returns:
        ScanResult com items ordenados por score descendente.
    """
    # 1. Obter top eventos (over-fetch para capturar sinais de PRR alto com volume baixo)
    fetch_limit = top_n * OVERFETCH_MULTIPLIER

    _using_bulk = use_bulk is True or (use_bulk is None and await _check_bulk_available())

    # Resolve role filter para event discovery
    role_filter_used: str | None = None

    if _using_bulk:
        from hypokrates.faers_bulk import api as bulk_api

        role_filter = _resolve_role_filter(primary_suspect_only, suspect_only)
        role_filter_used = role_filter.value

        raw_events = await bulk_api.bulk_top_events(
            drug, role_filter=role_filter, limit=fetch_limit
        )
        # Converter para AdverseEvent para compatibilidade
        events = [AdverseEvent(term=ev, count=cnt) for ev, cnt in raw_events]

        # Pre-fetch drug_total e n_total via bulk
        from hypokrates.faers_bulk.store import FAERSBulkStore

        store = FAERSBulkStore.get_instance()
        shared_drug_total, shared_n_total = await asyncio.gather(
            bulk_api.bulk_drug_total(drug, role_filter=role_filter),
            asyncio.to_thread(store.count_total),
        )
    else:
        if primary_suspect_only:
            logger.warning(
                "Scan %s: primary_suspect_only requires bulk; falling back to suspect_only",
                drug,
            )
        faers_result = await faers_api.top_events(
            drug, suspect_only=suspect_only, limit=fetch_limit, use_cache=use_cache
        )
        events = faers_result.events
        shared_drug_total = None
        shared_n_total = None

    # 1b. Filtrar termos operacionais/regulatórios MedDRA
    filtered_operational_count = 0
    if filter_operational and events:
        original_count = len(events)
        events = [ev for ev in events if ev.term.upper().strip() not in OPERATIONAL_MEDDRA_TERMS]
        filtered_operational_count = original_count - len(events)
        if filtered_operational_count > 0:
            logger.info(
                "Scan %s: filtered %d operational MedDRA terms",
                drug,
                filtered_operational_count,
            )

    if not events:
        return ScanResult(
            drug=drug,
            total_scanned=0,
            meta=MetaInfo(
                source="hypokrates/scan",
                query={"drug": drug, "top_n": top_n},
                total_results=0,
                retrieved_at=datetime.now(UTC),
                disclaimer="No adverse events found in FAERS for this drug.",
            ),
        )

    # 2. Pre-fetch drug-level data (1x por droga, não por evento)
    label_cache: LabelEventsResult | None = None
    drugbank_cache: DrugBankInfo | None = None
    ot_safety_cache: OTDrugSafety | None = None

    if check_labels:
        from hypokrates.dailymed import api as dailymed_api

        label_cache = await dailymed_api.label_events(drug, use_cache=use_cache)

    if check_drugbank:
        from hypokrates.drugbank import api as drugbank_api

        drugbank_cache = await drugbank_api.drug_info(drug)

    if check_opentargets:
        from hypokrates.opentargets import api as opentargets_api

        ot_safety_cache = await opentargets_api.drug_adverse_events(drug, use_cache=use_cache)

    chembl_cache: ChEMBLMechanism | None = None
    if check_chembl:
        from hypokrates.chembl import api as chembl_api

        chembl_cache = await chembl_api.drug_mechanism(drug, use_cache=use_cache)

    # 2b. Pre-computar valores FAERS compartilhados (1x por droga, não por evento)
    # Skip quando usando bulk — shared values já foram computados acima
    faers_client: FAERSClient | None = None
    drug_search: str | None = None

    if not _using_bulk:
        faers_client = FAERSClient()
        try:
            drug_search = await faers_api.resolve_drug_field(
                drug, client=faers_client, use_cache=use_cache
            )
            char_filter = (
                f" AND {DRUG_CHARACTERIZATION_FIELD}:{DRUG_CHARACTERIZATION_SUSPECT}"
                if suspect_only
                else ""
            )
            search_drug = f"{drug_search}{char_filter}"
            shared_drug_total, shared_n_total = await asyncio.gather(
                faers_client.fetch_total(search_drug, use_cache=use_cache),
                faers_client.fetch_total("", use_cache=use_cache),
            )
        except Exception:
            logger.warning(
                "Scan %s: pre-compute shared FAERS values failed, continuing without",
                drug,
            )

    # 3. Executar hypothesis() em paralelo com semáforo
    semaphore = asyncio.Semaphore(concurrency)
    completed = 0
    total = len(events)

    async def _run_hypothesis(event_term: str) -> HypothesisResult | Exception:
        nonlocal completed
        async with semaphore:
            try:
                result = await cross_api.hypothesis(
                    drug,
                    event_term,
                    use_cache=use_cache,
                    suspect_only=suspect_only,
                    use_bulk=use_bulk,
                    check_label=check_labels,
                    check_trials=check_trials,
                    check_drugbank=check_drugbank,
                    check_opentargets=check_opentargets,
                    check_chembl=check_chembl,
                    check_onsides=check_onsides,
                    check_pharmgkb=check_pharmgkb,
                    check_canada=check_canada,
                    check_jader=check_jader,
                    _label_cache=label_cache,
                    _drugbank_cache=drugbank_cache,
                    _ot_safety_cache=ot_safety_cache,
                    _chembl_cache=chembl_cache,
                    _faers_client=faers_client,
                    _drug_search=drug_search,
                    _drug_total=shared_drug_total,
                    _n_total=shared_n_total,
                )
            except Exception as exc:
                completed += 1
                logger.warning(
                    "Scan %s: %d/%d — %s FAILED: %s",
                    drug,
                    completed,
                    total,
                    event_term,
                    exc,
                )
                if on_progress is not None:
                    on_progress(completed, total, event_term)
                return exc
            else:
                completed += 1
                logger.info("Scan %s: %d/%d — %s", drug, completed, total, event_term)
                if on_progress is not None:
                    on_progress(completed, total, event_term)
                return result

    tasks = [_run_hypothesis(ev.term) for ev in events]
    try:
        results = await asyncio.gather(*tasks)
    finally:
        if faers_client is not None:
            await faers_client.close()

    # 3. Processar resultados
    items: list[ScanItem] = []
    failed_count = 0
    skipped_events: list[str] = []
    novel_count = 0
    emerging_count = 0
    known_count = 0
    no_signal_count = 0
    labeled_count = 0

    for i, res in enumerate(results):
        if isinstance(res, Exception):
            failed_count += 1
            skipped_events.append(events[i].term)
            continue

        hyp = res
        # Contar classificações
        if hyp.classification == HypothesisClassification.NOVEL_HYPOTHESIS:
            novel_count += 1
        elif hyp.classification == HypothesisClassification.EMERGING_SIGNAL:
            emerging_count += 1
        elif hyp.classification == HypothesisClassification.KNOWN_ASSOCIATION:
            known_count += 1
        else:
            no_signal_count += 1

        if hyp.in_label is True:
            labeled_count += 1

        # Filtrar NO_SIGNAL se não solicitado
        if not include_no_signal and hyp.classification == HypothesisClassification.NO_SIGNAL:
            continue

        score = _score(hyp)
        vol_flag = hyp.signal.table.a >= VOLUME_ANOMALY_THRESHOLD
        items.append(
            ScanItem(
                drug=drug,
                event=hyp.event,
                classification=hyp.classification,
                signal=hyp.signal,
                literature_count=hyp.literature_count,
                articles=hyp.articles,
                evidence=hyp.evidence,
                summary=hyp.summary,
                score=score,
                rank=0,  # atribuído abaixo
                in_label=hyp.in_label,
                active_trials=hyp.active_trials,
                mechanism=hyp.mechanism,
                ot_llr=hyp.ot_llr,
                volume_flag=vol_flag,
            )
        )

    # 4. Ordenar por score e reconstruir com ranks corretos
    items.sort(key=lambda x: x.score, reverse=True)

    # 5. MedDRA grouping (antes do truncate para agrupar corretamente)
    groups_applied = False
    if group_events and items:
        from hypokrates.vocab.meddra import group_scan_items

        grouped = group_scan_items(items)
        if len(grouped) < len(items):
            items = grouped
            groups_applied = True

    # 5a. Flag indication terms e penalizar score
    flagged_items: list[ScanItem] = []
    for item in items:
        if is_indication_term(item.event):
            flagged_items.append(
                item.model_copy(
                    update={
                        "is_indication": True,
                        "score": item.score * INDICATION_MULTIPLIER,
                    }
                )
            )
        else:
            flagged_items.append(item)
    items = flagged_items
    # Re-sort after score penalty
    items.sort(key=lambda x: x.score, reverse=True)

    # 5b. Co-administration analysis (Layer 1 only — Layer 2 é caro demais para N items)
    coadmin_flagged_count = 0
    if check_coadmin and items:
        coadmin_client: FAERSClient | None = None
        try:
            coadmin_client = FAERSClient()
            coadmin_drug_search = drug_search or await faers_api.resolve_drug_field(
                drug, client=coadmin_client, use_cache=use_cache
            )

            async def _run_coadmin(item: ScanItem) -> ScanItem:
                if not item.signal.signal_detected:
                    return item
                try:
                    profile = await faers_api.co_suspect_profile(
                        drug,
                        item.event,
                        suspect_only=suspect_only,
                        use_cache=use_cache,
                        _client=coadmin_client,
                        _drug_search=coadmin_drug_search,
                    )
                except Exception:
                    logger.warning("Scan %s: coadmin failed for %s", drug, item.event)
                    return item
                if profile.co_admin_flag:
                    top_drugs_str = ", ".join(n for n, _ in profile.top_co_drugs[:5])
                    return item.model_copy(
                        update={
                            "coadmin_flag": True,
                            "coadmin_detail": (
                                f"median {profile.median_suspects:.1f} co-suspects/report, "
                                f"top: {top_drugs_str}"
                            ),
                            "score": item.score * CO_ADMIN_MULTIPLIER,
                        }
                    )
                return item

            coadmin_sem = asyncio.Semaphore(concurrency)

            async def _guarded_coadmin(item: ScanItem) -> ScanItem:
                async with coadmin_sem:
                    return await _run_coadmin(item)

            items = list(await asyncio.gather(*[_guarded_coadmin(it) for it in items]))
            coadmin_flagged_count = sum(1 for it in items if it.coadmin_flag)
            items.sort(key=lambda x: x.score, reverse=True)
        finally:
            if coadmin_client is not None:
                await coadmin_client.close()

    # 5c. Direction analysis — compara PRR base vs PS-only (bulk only)
    if check_direction and _using_bulk:
        from hypokrates.faers_bulk.api import bulk_signal as _bulk_signal
        from hypokrates.faers_bulk.constants import RoleCodFilter as _RoleCodFilter

        direction_sem = asyncio.Semaphore(concurrency)

        async def _run_direction(item: ScanItem) -> ScanItem:
            if not item.signal.signal_detected:
                return item
            base_prr = item.signal.prr.value
            if base_prr <= 0:
                return item
            async with direction_sem:
                try:
                    ps_result = await _bulk_signal(
                        drug, item.event, role_filter=_RoleCodFilter.PS_ONLY
                    )
                except Exception:
                    logger.warning("Scan %s: direction failed for %s", drug, item.event)
                    return item
            ps_prr = ps_result.prr.value
            direction: str | None = None
            if ps_prr > base_prr * DIRECTION_STRENGTHENS_THRESHOLD:
                direction = "strengthens"
            elif ps_prr < base_prr * DIRECTION_WEAKENS_THRESHOLD:
                direction = "weakens"
            return item.model_copy(update={"ps_only_prr": ps_prr, "direction": direction})

        items = list(await asyncio.gather(*[_run_direction(it) for it in items]))

    # 5d. Truncar para top_n, atribuir ranks e clusters semânticos
    items = items[:top_n]
    items = [
        item.model_copy(update={"rank": idx + 1, "cluster": get_cluster(item.event)})
        for idx, item in enumerate(items)
    ]

    # 6. Enriquecer ScanResult com dados drug-level (DrugBank ou ChEMBL)
    scan_mechanism: str | None = None
    scan_interactions_count: int | None = None
    scan_cyp_enzymes: list[str] = []
    if drugbank_cache is not None:
        scan_mechanism = drugbank_cache.mechanism_of_action or None
        scan_interactions_count = len(drugbank_cache.interactions)
        scan_cyp_enzymes = [e.gene_name for e in drugbank_cache.enzymes if e.gene_name]
    if chembl_cache is not None and scan_mechanism is None:
        scan_mechanism = chembl_cache.mechanism_of_action or None
        if not scan_cyp_enzymes:
            for t in chembl_cache.targets:
                scan_cyp_enzymes.extend(g for g in t.gene_names if g not in scan_cyp_enzymes)

    return ScanResult(
        drug=drug,
        items=items,
        total_scanned=total,
        novel_count=novel_count,
        emerging_count=emerging_count,
        known_count=known_count,
        no_signal_count=no_signal_count,
        labeled_count=labeled_count,
        failed_count=failed_count,
        groups_applied=groups_applied,
        filtered_operational_count=filtered_operational_count,
        coadmin_flagged_count=coadmin_flagged_count,
        bulk_mode=_using_bulk,
        role_filter_used=role_filter_used,
        skipped_events=skipped_events,
        mechanism=scan_mechanism,
        interactions_count=scan_interactions_count,
        cyp_enzymes=scan_cyp_enzymes,
        meta=MetaInfo(
            source="hypokrates/scan",
            query={"drug": drug, "top_n": top_n},
            total_results=len(items),
            retrieved_at=datetime.now(UTC),
            disclaimer="Automated scan — clinical validation required. "
            "Scoring is a heuristic for prioritization, not clinical significance. "
            + SCAN_METHODOLOGY
            + " "
            + PRR_DISCLAIMER,
        ),
    )


def _resolve_role_filter(primary_suspect_only: bool, suspect_only: bool) -> RoleCodFilter:
    """Resolve flags booleanas para RoleCodFilter do bulk."""
    from hypokrates.faers_bulk.constants import RoleCodFilter

    if primary_suspect_only:
        return RoleCodFilter.PS_ONLY
    return RoleCodFilter.SUSPECT


async def _check_bulk_available() -> bool:
    """Verifica se FAERS Bulk está disponível (para auto-detect)."""
    try:
        from hypokrates.faers_bulk.api import is_bulk_available

        return await is_bulk_available()
    except (HypokratesError, ImportError):
        return False


def _score(result: HypothesisResult) -> float:
    """Calcula score de priorização para uma hipótese."""
    base = CLASSIFICATION_WEIGHTS.get(result.classification, 0.0)
    if base == 0.0:
        return 0.0
    prr_lci = max(result.signal.prr.ci_lower, 0.0)
    ror_lci = max(result.signal.ror.ci_lower, 0.0)
    strength = (prr_lci + ror_lci) / 2.0
    score = base * max(strength, 0.1)

    # Ajustar score por label
    if result.in_label is False:
        score *= LABEL_NOT_IN_MULTIPLIER
    elif result.in_label is True:
        score *= LABEL_IN_MULTIPLIER

    return score
