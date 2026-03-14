"""API pública do módulo scan — async-first."""

from __future__ import annotations

import asyncio
import logging
from datetime import UTC, datetime
from typing import TYPE_CHECKING

from hypokrates.cross import api as cross_api
from hypokrates.cross.models import HypothesisClassification, HypothesisResult
from hypokrates.faers import api as faers_api
from hypokrates.models import MetaInfo
from hypokrates.scan.constants import (
    CLASSIFICATION_WEIGHTS,
    DEFAULT_CONCURRENCY,
    DEFAULT_TOP_N,
    SCAN_METHODOLOGY,
)
from hypokrates.scan.models import ScanItem, ScanResult

if TYPE_CHECKING:
    from collections.abc import Callable

logger = logging.getLogger(__name__)


async def scan_drug(
    drug: str,
    *,
    top_n: int = DEFAULT_TOP_N,
    concurrency: int = DEFAULT_CONCURRENCY,
    include_no_signal: bool = False,
    use_cache: bool = True,
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
        on_progress: Callback opcional (completed, total, event_term).

    Returns:
        ScanResult com items ordenados por score descendente.
    """
    # 1. Obter top eventos
    faers_result = await faers_api.top_events(drug, limit=top_n, use_cache=use_cache)
    events = faers_result.events

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

    # 2. Executar hypothesis() em paralelo com semáforo
    semaphore = asyncio.Semaphore(concurrency)
    completed = 0
    total = len(events)

    async def _run_hypothesis(event_term: str) -> HypothesisResult | Exception:
        nonlocal completed
        async with semaphore:
            try:
                result = await cross_api.hypothesis(drug, event_term, use_cache=use_cache)
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
    results = await asyncio.gather(*tasks)

    # 3. Processar resultados
    items: list[ScanItem] = []
    failed_count = 0
    skipped_events: list[str] = []
    novel_count = 0
    emerging_count = 0
    known_count = 0
    no_signal_count = 0

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

        # Filtrar NO_SIGNAL se não solicitado
        if not include_no_signal and hyp.classification == HypothesisClassification.NO_SIGNAL:
            continue

        score = _score(hyp)
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
            )
        )

    # 4. Ordenar por score e reconstruir com ranks corretos
    items.sort(key=lambda x: x.score, reverse=True)
    items = [item.model_copy(update={"rank": idx + 1}) for idx, item in enumerate(items)]

    return ScanResult(
        drug=drug,
        items=items,
        total_scanned=total,
        novel_count=novel_count,
        emerging_count=emerging_count,
        known_count=known_count,
        no_signal_count=no_signal_count,
        failed_count=failed_count,
        skipped_events=skipped_events,
        meta=MetaInfo(
            source="hypokrates/scan",
            query={"drug": drug, "top_n": top_n},
            total_results=len(items),
            retrieved_at=datetime.now(UTC),
            disclaimer="Automated scan — clinical validation required. "
            "Scoring is a heuristic for prioritization, not clinical significance. "
            + SCAN_METHODOLOGY,
        ),
    )


def _score(result: HypothesisResult) -> float:
    """Calcula score de priorização para uma hipótese."""
    base = CLASSIFICATION_WEIGHTS.get(result.classification, 0.0)
    if base == 0.0:
        return 0.0
    prr_lci = max(result.signal.prr.ci_lower, 0.0)
    ror_lci = max(result.signal.ror.ci_lower, 0.0)
    strength = (prr_lci + ror_lci) / 2.0
    return base * max(strength, 0.1)
