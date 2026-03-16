"""Comparação intra-classe automatizada de sinais de farmacovigilância."""

from __future__ import annotations

import asyncio
import logging
import statistics as _statistics
from datetime import UTC, datetime
from typing import TYPE_CHECKING

from hypokrates.exceptions import ValidationError
from hypokrates.faers import api as faers_api
from hypokrates.faers.client import FAERSClient
from hypokrates.faers.constants import (
    DRUG_CHARACTERIZATION_FIELD,
    DRUG_CHARACTERIZATION_SUSPECT,
)
from hypokrates.models import MetaInfo
from hypokrates.scan.constants import (
    CLASS_EFFECT_THRESHOLD,
    DEFAULT_CLASS_CONCURRENCY,
    DEFAULT_CLASS_TOP_N,
    OPERATIONAL_MEDDRA_TERMS,
    OUTLIER_FACTOR,
    PRR_DISCLAIMER,
)
from hypokrates.scan.models import (
    ClassCompareResult,
    ClassEventItem,
    EventClassification,
)
from hypokrates.stats import api as stats_api
from hypokrates.vocab.meddra import canonical_term

if TYPE_CHECKING:
    from hypokrates.stats.models import SignalResult

logger = logging.getLogger(__name__)

_MIN_DRUGS = 2


async def compare_class(
    drugs: list[str],
    *,
    top_n: int = DEFAULT_CLASS_TOP_N,
    class_threshold: float = CLASS_EFFECT_THRESHOLD,
    outlier_factor: float = OUTLIER_FACTOR,
    concurrency: int = DEFAULT_CLASS_CONCURRENCY,
    filter_operational: bool = True,
    suspect_only: bool = False,
    use_bulk: bool | None = None,
    use_cache: bool = True,
) -> ClassCompareResult:
    """Compara sinais de eventos adversos entre N drogas da mesma classe.

    Classifica cada evento como class_effect (>=75% das drogas),
    drug_specific (1 droga), ou differential (varia significativamente).

    Args:
        drugs: Lista de nomes genéricos (min 2).
        top_n: Número de top eventos por droga para incluir na união.
        class_threshold: Fração mínima de drogas com sinal para class_effect.
        outlier_factor: PRR max/median acima do qual é outlier.
        concurrency: Máximo de signal() simultâneos.
        filter_operational: Se deve filtrar termos MedDRA operacionais.
        suspect_only: Se True, conta apenas reports onde a droga é suspect.
        use_bulk: None=auto-detect, True=forçar bulk, False=forçar API.
        use_cache: Se deve usar cache.

    Returns:
        ClassCompareResult com eventos classificados.
    """
    if len(drugs) < _MIN_DRUGS:
        raise ValidationError(
            "drugs", f"compare_class requires at least {_MIN_DRUGS}, got {len(drugs)}"
        )

    # 1. Fetch top events per drug (paralelo)
    top_results = await asyncio.gather(
        *[
            faers_api.top_events(drug, suspect_only=suspect_only, limit=top_n, use_cache=use_cache)
            for drug in drugs
        ]
    )

    # 2. Build event union com canonical_term para dedup
    event_union: set[str] = set()
    for result in top_results:
        for ev in result.events:
            event_union.add(canonical_term(ev.term))

    # 2b. Filtrar termos operacionais
    if filter_operational:
        before = len(event_union)
        event_union = {e for e in event_union if e.upper().strip() not in OPERATIONAL_MEDDRA_TERMS}
        filtered = before - len(event_union)
        if filtered > 0:
            logger.info("compare_class: filtered %d operational terms", filtered)

    if not event_union:
        return _empty_result(drugs, class_threshold, outlier_factor)

    events = sorted(event_union)

    # 3. Pre-compute FAERS shared data (paralelo)
    client = FAERSClient()
    try:
        drug_data, n_total = await _precompute_drug_data(
            drugs, client=client, suspect_only=suspect_only, use_cache=use_cache
        )

        # 4. Build signal matrix (paralelo com semaphore)
        matrix = await _build_signal_matrix(
            drugs,
            events,
            drug_data=drug_data,
            n_total=n_total,
            client=client,
            concurrency=concurrency,
            suspect_only=suspect_only,
            use_bulk=use_bulk,
            use_cache=use_cache,
        )
    finally:
        await client.close()

    # 5. Classify events
    items = _classify_events(drugs, events, matrix, class_threshold, outlier_factor)

    class_count = sum(1 for it in items if it.classification == EventClassification.CLASS_EFFECT)
    specific_count = sum(
        1 for it in items if it.classification == EventClassification.DRUG_SPECIFIC
    )
    diff_count = sum(1 for it in items if it.classification == EventClassification.DIFFERENTIAL)

    return ClassCompareResult(
        drugs=drugs,
        items=items,
        class_effect_count=class_count,
        drug_specific_count=specific_count,
        differential_count=diff_count,
        total_events=len(items),
        class_threshold_used=class_threshold,
        outlier_factor_used=outlier_factor,
        meta=MetaInfo(
            source="hypokrates/compare_class",
            query={"drugs": ",".join(drugs), "top_n": top_n},
            total_results=len(items),
            retrieved_at=datetime.now(UTC),
            disclaimer="Intra-class comparison of FAERS disproportionality signals. "
            "Classification is heuristic — clinical validation required. " + PRR_DISCLAIMER,
        ),
    )


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


class _DrugData:
    """Dados pre-computados por droga para reutilizar em signal()."""

    __slots__ = ("drug_search", "drug_total")

    def __init__(self, drug_search: str | None, drug_total: int | None) -> None:
        self.drug_search = drug_search
        self.drug_total = drug_total


async def _precompute_drug_data(
    drugs: list[str],
    *,
    client: FAERSClient,
    suspect_only: bool,
    use_cache: bool,
) -> tuple[dict[str, _DrugData], int | None]:
    """Resolve drug field e fetch_total para cada droga em paralelo.

    Returns:
        Tupla (drug_data_map, n_total).
    """
    result: dict[str, _DrugData] = {}

    async def _resolve(drug: str) -> tuple[str, str | None, int | None]:
        try:
            drug_search = await faers_api.resolve_drug_field(
                drug, client=client, use_cache=use_cache
            )
            char_filter = (
                f" AND {DRUG_CHARACTERIZATION_FIELD}:{DRUG_CHARACTERIZATION_SUSPECT}"
                if suspect_only
                else ""
            )
            search_drug = f"{drug_search}{char_filter}"
            drug_total = await client.fetch_total(search_drug, use_cache=use_cache)
        except Exception:
            logger.warning("compare_class: pre-compute for %s failed", drug)
            return drug, None, None
        else:
            return drug, drug_search, drug_total

    resolved = await asyncio.gather(*[_resolve(d) for d in drugs])
    for drug, drug_search, drug_total in resolved:
        result[drug] = _DrugData(drug_search, drug_total)

    # n_total compartilhado (global)
    n_total: int | None = None
    try:
        n_total = await client.fetch_total("", use_cache=use_cache)
    except Exception:
        logger.warning("compare_class: fetch n_total failed")

    return result, n_total


async def _build_signal_matrix(
    drugs: list[str],
    events: list[str],
    *,
    drug_data: dict[str, _DrugData],
    n_total: int | None,
    client: FAERSClient,
    concurrency: int,
    suspect_only: bool,
    use_bulk: bool | None = None,
    use_cache: bool,
) -> dict[str, dict[str, SignalResult | None]]:
    """Roda signal() para cada (drug, event) com semaphore."""
    semaphore = asyncio.Semaphore(concurrency)
    matrix: dict[str, dict[str, SignalResult | None]] = {d: {} for d in drugs}

    async def _signal_one(drug: str, event: str) -> tuple[str, str, SignalResult | None]:
        async with semaphore:
            dd = drug_data.get(drug)
            try:
                sig = await stats_api.signal(
                    drug,
                    event,
                    suspect_only=suspect_only,
                    use_bulk=use_bulk,
                    use_cache=use_cache,
                    _client=client,
                    _drug_search=dd.drug_search if dd else None,
                    _drug_total=dd.drug_total if dd else None,
                    _n_total=n_total,
                )
            except Exception:
                logger.warning("compare_class: signal(%s, %s) failed", drug, event)
                return drug, event, None
            else:
                return drug, event, sig

    tasks = [_signal_one(d, e) for d in drugs for e in events]
    results = await asyncio.gather(*tasks)

    for drug, event, sig in results:
        matrix[drug][event] = sig

    return matrix


def _classify_events(
    drugs: list[str],
    events: list[str],
    matrix: dict[str, dict[str, SignalResult | None]],
    class_threshold: float,
    outlier_factor_val: float,
) -> list[ClassEventItem]:
    """Classifica cada evento baseado na matriz de sinais."""
    items: list[ClassEventItem] = []

    for event in events:
        signals: dict[str, SignalResult] = {}
        prr_values: dict[str, float] = {}
        drugs_with: list[str] = []
        drugs_without: list[str] = []

        for drug in drugs:
            sig = matrix[drug].get(event)
            if sig is None:
                drugs_without.append(drug)
                continue
            signals[drug] = sig
            prr_values[drug] = sig.prr.value
            if sig.signal_detected:
                drugs_with.append(drug)
            else:
                drugs_without.append(drug)

        if not signals:
            continue

        count = len(drugs_with)
        ratio = count / len(drugs)

        # PRR stats
        detected_prr = [prr_values[d] for d in drugs_with] if drugs_with else []
        max_prr = max(prr_values.values()) if prr_values else 0.0
        median_prr = _statistics.median(detected_prr) if len(detected_prr) >= 1 else 0.0

        strongest = max(prr_values, key=prr_values.get) if prr_values else None  # type: ignore[arg-type]

        outlier_drug: str | None = None
        computed_outlier_factor: float | None = None

        if ratio >= class_threshold:
            # Checar outlier: max_prr > outlier_factor * median_prr
            if median_prr > 0 and max_prr > outlier_factor_val * median_prr:
                classification = EventClassification.DIFFERENTIAL
                outlier_drug = strongest
                computed_outlier_factor = round(max_prr / median_prr, 2)
            else:
                classification = EventClassification.CLASS_EFFECT
        elif count == 1:
            classification = EventClassification.DRUG_SPECIFIC
        elif count == 0:
            continue
        else:
            classification = EventClassification.DIFFERENTIAL

        items.append(
            ClassEventItem(
                event=event,
                classification=classification,
                signals=signals,
                drugs_with_signal=drugs_with,
                drugs_without_signal=drugs_without,
                strongest_drug=strongest,
                prr_values=prr_values,
                max_prr=round(max_prr, 2),
                median_prr=round(median_prr, 2),
                outlier_drug=outlier_drug,
                outlier_factor=computed_outlier_factor,
            )
        )

    # Ordenar: class_effect primeiro, depois drug_specific, depois differential
    # Dentro de cada grupo: por max_prr descendente
    _order = {
        EventClassification.CLASS_EFFECT: 0,
        EventClassification.DRUG_SPECIFIC: 1,
        EventClassification.DIFFERENTIAL: 2,
    }
    items.sort(key=lambda x: (_order[x.classification], -x.max_prr))
    return items


def _empty_result(
    drugs: list[str],
    class_threshold: float,
    outlier_factor_val: float,
) -> ClassCompareResult:
    return ClassCompareResult(
        drugs=drugs,
        class_threshold_used=class_threshold,
        outlier_factor_used=outlier_factor_val,
        meta=MetaInfo(
            source="hypokrates/compare_class",
            query={"drugs": ",".join(drugs)},
            total_results=0,
            retrieved_at=datetime.now(UTC),
            disclaimer="No events found for comparison.",
        ),
    )
