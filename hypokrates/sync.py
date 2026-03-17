"""Sync wrappers para a API async do hypokrates.

Permite uso síncrono:
    from hypokrates.sync import faers
    result = faers.adverse_events("propofol")
"""

from __future__ import annotations

import asyncio
import functools
from typing import TYPE_CHECKING, Any, TypeVar

from hypokrates.anvisa import api as anvisa_api
from hypokrates.canada import api as canada_api
from hypokrates.chembl import api as chembl_api
from hypokrates.cross import api as cross_api
from hypokrates.dailymed import api as dailymed_api
from hypokrates.drugbank import api as drugbank_api
from hypokrates.faers import api as faers_api
from hypokrates.faers_bulk import api as faers_bulk_api
from hypokrates.jader import api as jader_api
from hypokrates.onsides import api as onsides_api
from hypokrates.opentargets import api as opentargets_api
from hypokrates.pharmgkb import api as pharmgkb_api
from hypokrates.pubmed import api as pubmed_api
from hypokrates.scan import api as scan_api
from hypokrates.scan import class_compare as class_compare_api
from hypokrates.stats import api as stats_api
from hypokrates.trials import api as trials_api
from hypokrates.vocab import api as vocab_api

if TYPE_CHECKING:
    from collections.abc import Callable, Coroutine

T = TypeVar("T")


def _run_sync(coro: Coroutine[Any, Any, T]) -> T:
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        loop = None

    if loop is not None and loop.is_running():
        import concurrent.futures

        with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
            future = pool.submit(asyncio.run, coro)
            return future.result()
    else:
        return asyncio.run(coro)


def _make_sync(fn: Callable[..., Coroutine[Any, Any, T]]) -> Callable[..., T]:
    @functools.wraps(fn)
    def wrapper(*args: Any, **kwargs: Any) -> T:
        return _run_sync(fn(*args, **kwargs))

    return wrapper


class _SyncFAERS:
    adverse_events = staticmethod(_make_sync(faers_api.adverse_events))
    top_events = staticmethod(_make_sync(faers_api.top_events))
    compare = staticmethod(_make_sync(faers_api.compare))
    drugs_by_event = staticmethod(_make_sync(faers_api.drugs_by_event))
    co_suspect_profile = staticmethod(_make_sync(faers_api.co_suspect_profile))


class _SyncStats:
    signal = staticmethod(_make_sync(stats_api.signal))
    signal_timeline = staticmethod(_make_sync(stats_api.signal_timeline))


class _SyncPubMed:
    count_papers = staticmethod(_make_sync(pubmed_api.count_papers))
    search_papers = staticmethod(_make_sync(pubmed_api.search_papers))


class _SyncCross:
    hypothesis = staticmethod(_make_sync(cross_api.hypothesis))
    compare_signals = staticmethod(_make_sync(cross_api.compare_signals))
    coadmin_analysis = staticmethod(_make_sync(cross_api.coadmin_analysis))


class _SyncScan:
    scan_drug = staticmethod(_make_sync(scan_api.scan_drug))
    compare_class = staticmethod(_make_sync(class_compare_api.compare_class))


class _SyncVocab:
    normalize_drug = staticmethod(_make_sync(vocab_api.normalize_drug))
    map_to_mesh = staticmethod(_make_sync(vocab_api.map_to_mesh))


class _SyncDailyMed:
    label_events = staticmethod(_make_sync(dailymed_api.label_events))
    check_label = staticmethod(_make_sync(dailymed_api.check_label))


class _SyncTrials:
    search_trials = staticmethod(_make_sync(trials_api.search_trials))


class _SyncDrugBank:
    drug_info = staticmethod(_make_sync(drugbank_api.drug_info))
    drug_interactions = staticmethod(_make_sync(drugbank_api.drug_interactions))
    drug_mechanism = staticmethod(_make_sync(drugbank_api.drug_mechanism))


class _SyncOpenTargets:
    drug_adverse_events = staticmethod(_make_sync(opentargets_api.drug_adverse_events))
    drug_safety_score = staticmethod(_make_sync(opentargets_api.drug_safety_score))


faers = _SyncFAERS()
stats = _SyncStats()
pubmed = _SyncPubMed()
cross = _SyncCross()
scan = _SyncScan()
vocab = _SyncVocab()
dailymed = _SyncDailyMed()
trials = _SyncTrials()


class _SyncChEMBL:
    drug_mechanism = staticmethod(_make_sync(chembl_api.drug_mechanism))
    drug_targets = staticmethod(_make_sync(chembl_api.drug_targets))
    drug_metabolism = staticmethod(_make_sync(chembl_api.drug_metabolism))


class _SyncFAERSBulk:
    is_bulk_available = staticmethod(_make_sync(faers_bulk_api.is_bulk_available))
    bulk_store_status = staticmethod(_make_sync(faers_bulk_api.bulk_store_status))
    bulk_signal = staticmethod(_make_sync(faers_bulk_api.bulk_signal))
    bulk_top_events = staticmethod(_make_sync(faers_bulk_api.bulk_top_events))
    bulk_drug_total = staticmethod(_make_sync(faers_bulk_api.bulk_drug_total))


class _SyncAnvisa:
    buscar_medicamento = staticmethod(_make_sync(anvisa_api.buscar_medicamento))
    buscar_por_substancia = staticmethod(_make_sync(anvisa_api.buscar_por_substancia))
    listar_apresentacoes = staticmethod(_make_sync(anvisa_api.listar_apresentacoes))
    mapear_nome = staticmethod(_make_sync(anvisa_api.mapear_nome))


class _SyncOnSIDES:
    onsides_events = staticmethod(_make_sync(onsides_api.onsides_events))
    onsides_check_event = staticmethod(_make_sync(onsides_api.onsides_check_event))


drugbank = _SyncDrugBank()
onsides = _SyncOnSIDES()
opentargets = _SyncOpenTargets()


class _SyncPharmGKB:
    pgx_annotations = staticmethod(_make_sync(pharmgkb_api.pgx_annotations))
    pgx_guidelines = staticmethod(_make_sync(pharmgkb_api.pgx_guidelines))
    pgx_drug_info = staticmethod(_make_sync(pharmgkb_api.pgx_drug_info))


pharmgkb = _SyncPharmGKB()
chembl = _SyncChEMBL()
faers_bulk = _SyncFAERSBulk()


class _SyncCanada:
    canada_signal = staticmethod(_make_sync(canada_api.canada_signal))
    canada_top_events = staticmethod(_make_sync(canada_api.canada_top_events))
    canada_bulk_status = staticmethod(_make_sync(canada_api.canada_bulk_status))


class _SyncJADER:
    jader_signal = staticmethod(_make_sync(jader_api.jader_signal))
    jader_top_events = staticmethod(_make_sync(jader_api.jader_top_events))
    jader_bulk_status = staticmethod(_make_sync(jader_api.jader_bulk_status))


anvisa = _SyncAnvisa()
canada = _SyncCanada()
jader = _SyncJADER()
