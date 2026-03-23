"""Base HTTP client com cache, rate limiting, retry e lifecycle."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any, Self

from hypokrates.cache import CacheStore, cache_key
from hypokrates.config import get_config
from hypokrates.constants import ParamsType as ParamsType  # noqa: TC001 — explicit re-export
from hypokrates.exceptions import ParseError
from hypokrates.http.rate_limiter import RateLimiter
from hypokrates.http.retry import retry_request
from hypokrates.http.settings import create_client

if TYPE_CHECKING:
    import httpx

logger = logging.getLogger(__name__)


class BaseClient:
    """Client HTTP base com cache transparente, rate limiting e retry.

    Subclasses herdam:
    - ``_get_client()`` — criação lazy do httpx.AsyncClient
    - ``close()`` / ``__aenter__`` / ``__aexit__`` — lifecycle
    - ``_cached_get()`` — GET com cache + rate limit + retry + parse
    - ``_parse_response()`` — JSON parse (override para error handling)
    """

    def __init__(
        self,
        *,
        source: str,
        base_url: str = "",
        rate: int,
        rate_source: str | None = None,
    ) -> None:
        self._source = source
        self._base_url = base_url
        self._client: httpx.AsyncClient | None = None
        self._rate_limiter = RateLimiter.for_source(rate_source or source, rate)

    async def _get_client(self) -> httpx.AsyncClient:
        """Cria (lazy) ou retorna o httpx.AsyncClient."""
        if self._client is None:
            self._client = create_client(base_url=self._base_url)
        return self._client

    async def close(self) -> None:
        """Fecha o client HTTP."""
        if self._client is not None:
            await self._client.aclose()
            self._client = None

    async def __aenter__(self) -> Self:
        """Entra no context manager."""
        return self

    async def __aexit__(self, *args: object) -> None:
        """Sai do context manager e fecha o client."""
        await self.close()

    async def _cache_lookup(
        self,
        endpoint: str,
        params: ParamsType | None = None,
        *,
        use_cache: bool = True,
        cache_source: str | None = None,
    ) -> tuple[str, dict[str, Any] | None]:
        """Check cache. Returns (key, cached_data_or_None). key="" if cache disabled."""
        src = cache_source or self._source
        if not (use_cache and get_config().cache_enabled):
            return "", None
        key = cache_key(src, endpoint, params)
        store = CacheStore.get_instance()
        cached = await store.aget(key)
        if cached is not None:
            logger.debug("Cache hit: %s", key)
        return key, cached

    async def _cache_store(
        self,
        key: str,
        data: dict[str, Any],
        *,
        cache_source: str | None = None,
    ) -> None:
        """Store data in cache. No-op if key is empty (cache disabled)."""
        if not key:
            return
        src = cache_source or self._source
        store = CacheStore.get_instance()
        await store.aset(key, data, src)

    async def _cached_get(
        self,
        endpoint: str,
        params: ParamsType | None = None,
        *,
        use_cache: bool = True,
        cache_suffix: str = "",
        cache_source: str | None = None,
        headers: dict[str, str] | None = None,
    ) -> dict[str, Any]:
        """GET com cache + rate limit + retry + parse."""
        cache_ep = f"{endpoint}{cache_suffix}" if cache_suffix else endpoint
        key, cached = await self._cache_lookup(
            cache_ep,
            params,
            use_cache=use_cache,
            cache_source=cache_source,
        )
        if cached is not None:
            return cached

        await self._rate_limiter.acquire()
        client = await self._get_client()
        response = await retry_request(
            client,
            "GET",
            endpoint,
            params=params,
            headers=headers,
            source_name=self._source,
        )

        data = self._parse_response(response)
        await self._cache_store(key, data, cache_source=cache_source)
        return data

    def _parse_response(self, response: httpx.Response) -> dict[str, Any]:
        """JSON parse padrão. Subclasses podem override para error handling."""
        try:
            data: dict[str, Any] = response.json()
        except Exception as exc:
            raise ParseError(self._source, f"Invalid JSON: {exc}") from exc
        return data
