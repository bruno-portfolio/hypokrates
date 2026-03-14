"""Sync wrappers para a API async do hypokrates.

Permite uso síncrono:
    from hypokrates.sync import faers
    result = faers.adverse_events("propofol")
"""

from __future__ import annotations

import asyncio
import functools
from typing import TYPE_CHECKING, Any, TypeVar

from hypokrates.cross import api as cross_api
from hypokrates.dailymed import api as dailymed_api
from hypokrates.faers import api as faers_api
from hypokrates.pubmed import api as pubmed_api
from hypokrates.scan import api as scan_api
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


class _SyncStats:
    """Wrapper síncrono para hypokrates.stats."""

    signal = staticmethod(_make_sync(stats_api.signal))


class _SyncPubMed:
    """Wrapper síncrono para hypokrates.pubmed."""

    count_papers = staticmethod(_make_sync(pubmed_api.count_papers))
    search_papers = staticmethod(_make_sync(pubmed_api.search_papers))


class _SyncCross:
    """Wrapper síncrono para hypokrates.cross."""

    hypothesis = staticmethod(_make_sync(cross_api.hypothesis))


class _SyncScan:
    """Wrapper síncrono para hypokrates.scan."""

    scan_drug = staticmethod(_make_sync(scan_api.scan_drug))


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


faers = _SyncFAERS()
stats = _SyncStats()
pubmed = _SyncPubMed()
cross = _SyncCross()
scan = _SyncScan()
vocab = _SyncVocab()
dailymed = _SyncDailyMed()
trials = _SyncTrials()
