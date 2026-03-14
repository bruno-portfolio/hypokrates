"""Sync wrappers para a API async do hypokrates.

Permite uso síncrono:
    from hypokrates.sync import faers
    result = faers.adverse_events("propofol")
"""

from __future__ import annotations

import asyncio
import functools
from typing import TYPE_CHECKING, Any, TypeVar

from hypokrates.faers import api as faers_api
from hypokrates.stats import api as stats_api

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


faers = _SyncFAERS()
stats = _SyncStats()
