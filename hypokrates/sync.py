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
from hypokrates.chembl import api as chembl_api
from hypokrates.cross import api as cross_api
from hypokrates.dailymed import api as dailymed_api
from hypokrates.drugbank import api as drugbank_api
from hypokrates.faers import api as faers_api
from hypokrates.faers_bulk import api as faers_bulk_api
from hypokrates.opentargets import api as opentargets_api
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
    """Executa coroutine de forma síncrona."""
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
    """Transforma função async em sync."""

    @functools.wraps(fn)
    def wrapper(*args: Any, **kwargs: Any) -> T:
        return _run_sync(fn(*args, **kwargs))

    return wrapper


class _SyncFAERS:
    """Wrapper síncrono para hypokrates.faers."""

    adverse_events = staticmethod(_make_sync(faers_api.adverse_events))
    top_events = staticmethod(_make_sync(faers_api.top_events))
    compare = staticmethod(_make_sync(faers_api.compare))
    drugs_by_event = staticmethod(_make_sync(faers_api.drugs_by_event))
    co_suspect_profile = staticmethod(_make_sync(faers_api.co_suspect_profile))


class _SyncStats:
    """Wrapper síncrono para hypokrates.stats."""

    signal = staticmethod(_make_sync(stats_api.signal))
    signal_timeline = staticmethod(_make_sync(stats_api.signal_timeline))


class _SyncPubMed:
    """Wrapper síncrono para hypokrates.pubmed."""

    count_papers = staticmethod(_make_sync(pubmed_api.count_papers))
    search_papers = staticmethod(_make_sync(pubmed_api.search_papers))


class _SyncCross:
    """Wrapper síncrono para hypokrates.cross."""

    hypothesis = staticmethod(_make_sync(cross_api.hypothesis))
    compare_signals = staticmethod(_make_sync(cross_api.compare_signals))
    coadmin_analysis = staticmethod(_make_sync(cross_api.coadmin_analysis))


class _SyncScan:
    """Wrapper síncrono para hypokrates.scan."""

    scan_drug = staticmethod(_make_sync(scan_api.scan_drug))
    compare_class = staticmethod(_make_sync(class_compare_api.compare_class))


class _SyncVocab:
    """Wrapper síncrono para hypokrates.vocab."""

    normalize_drug = staticmethod(_make_sync(vocab_api.normalize_drug))
    map_to_mesh = staticmethod(_make_sync(vocab_api.map_to_mesh))


class _SyncDailyMed:
    """Wrapper síncrono para hypokrates.dailymed."""

    label_events = staticmethod(_make_sync(dailymed_api.label_events))
    check_label = staticmethod(_make_sync(dailymed_api.check_label))


class _SyncTrials:
    """Wrapper síncrono para hypokrates.trials."""

    search_trials = staticmethod(_make_sync(trials_api.search_trials))


class _SyncDrugBank:
    """Wrapper síncrono para hypokrates.drugbank."""

    drug_info = staticmethod(_make_sync(drugbank_api.drug_info))
    drug_interactions = staticmethod(_make_sync(drugbank_api.drug_interactions))
    drug_mechanism = staticmethod(_make_sync(drugbank_api.drug_mechanism))


class _SyncOpenTargets:
    """Wrapper síncrono para hypokrates.opentargets."""

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
    """Wrapper síncrono para hypokrates.chembl."""

    drug_mechanism = staticmethod(_make_sync(chembl_api.drug_mechanism))
    drug_targets = staticmethod(_make_sync(chembl_api.drug_targets))
    drug_metabolism = staticmethod(_make_sync(chembl_api.drug_metabolism))


class _SyncFAERSBulk:
    """Wrapper síncrono para hypokrates.faers_bulk."""

    is_bulk_available = staticmethod(_make_sync(faers_bulk_api.is_bulk_available))
    bulk_store_status = staticmethod(_make_sync(faers_bulk_api.bulk_store_status))
    bulk_signal = staticmethod(_make_sync(faers_bulk_api.bulk_signal))
    bulk_top_events = staticmethod(_make_sync(faers_bulk_api.bulk_top_events))
    bulk_drug_total = staticmethod(_make_sync(faers_bulk_api.bulk_drug_total))


class _SyncAnvisa:
    """Wrapper sincrono para hypokrates.anvisa."""

    buscar_medicamento = staticmethod(_make_sync(anvisa_api.buscar_medicamento))
    buscar_por_substancia = staticmethod(_make_sync(anvisa_api.buscar_por_substancia))
    listar_apresentacoes = staticmethod(_make_sync(anvisa_api.listar_apresentacoes))
    mapear_nome = staticmethod(_make_sync(anvisa_api.mapear_nome))


drugbank = _SyncDrugBank()
opentargets = _SyncOpenTargets()
chembl = _SyncChEMBL()
faers_bulk = _SyncFAERSBulk()
anvisa = _SyncAnvisa()
