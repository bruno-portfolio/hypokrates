"""HTTP client para OpenFDA FAERS API."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

from hypokrates.cache import CacheStore, cache_key
from hypokrates.config import get_config
from hypokrates.constants import OPENFDA_BASE_URL, HTTPSettings, Source
from hypokrates.exceptions import ParseError, SourceUnavailableError
from hypokrates.faers.constants import DEFAULT_COUNT_LIMIT, DEFAULT_LIMIT, DRUG_EVENT_ENDPOINT
from hypokrates.http.rate_limiter import RateLimiter
from hypokrates.http.retry import retry_request
from hypokrates.http.settings import create_client

if TYPE_CHECKING:
    import httpx

logger = logging.getLogger(__name__)


class FAERSClient:
    """Client HTTP para a API OpenFDA drug/event.

    Gerencia rate limiting, retry, e cache transparente.
    """

    def __init__(self) -> None:
        self._client: httpx.AsyncClient | None = None
        cfg = get_config()

        rate = HTTPSettings.RATE_LIMITS.get(Source.FAERS, 40)
        if cfg.openfda_api_key:
            rate = 240
        self._rate_limiter = RateLimiter.for_source(Source.FAERS, rate)

    async def _get_client(self) -> httpx.AsyncClient:
        if self._client is None:
            self._client = create_client(base_url=OPENFDA_BASE_URL)
        return self._client

    async def fetch(
        self,
        search: str,
        *,
        limit: int = DEFAULT_LIMIT,
        skip: int = 0,
        use_cache: bool = True,
    ) -> dict[str, Any]:
        """Busca reports no OpenFDA.

        Args:
            search: Query string OpenFDA (e.g., 'patient.drug.openfda.generic_name:"propofol"')
            limit: Máximo de resultados por página.
            skip: Offset para paginação.
            use_cache: Se deve usar cache.

        Returns:
            JSON response completo do OpenFDA.
        """
        params = self._build_params(search, limit=limit, skip=skip)

        # Cache lookup
        if use_cache and get_config().cache_enabled:
            key = cache_key(Source.FAERS, DRUG_EVENT_ENDPOINT, params)
            store = CacheStore.get_instance()
            cached = store.get(key)
            if cached is not None:
                logger.debug("Cache hit: %s", key)
                return cached
        # Rate limit + request
        await self._rate_limiter.acquire()
        client = await self._get_client()
        response = await retry_request(
            client,
            "GET",
            DRUG_EVENT_ENDPOINT,
            params=params,
            source_name=Source.FAERS,
        )

        try:
            data: dict[str, Any] = response.json()
        except Exception as exc:
            raise ParseError(Source.FAERS, f"Invalid JSON: {exc}") from exc

        if "error" in data:
            error_msg = data["error"].get("message", "Unknown error")
            if "No matches found" in str(error_msg):
                data = {"meta": {"results": {"total": 0}}, "results": []}
            else:
                raise SourceUnavailableError(Source.FAERS, str(error_msg))

        # Cache store
        if use_cache and get_config().cache_enabled:
            key = cache_key(Source.FAERS, DRUG_EVENT_ENDPOINT, params)
            store = CacheStore.get_instance()
            store.set(key, data, Source.FAERS)

        return data

    async def fetch_count(
        self,
        search: str,
        count_field: str,
        *,
        limit: int = DEFAULT_COUNT_LIMIT,
        use_cache: bool = True,
    ) -> dict[str, Any]:
        """Busca contagens agregadas no OpenFDA.

        Args:
            search: Query string OpenFDA.
            count_field: Campo para agregar (e.g., 'patient.reaction.reactionmeddrapt.exact').
            limit: Máximo de buckets retornados.
            use_cache: Se deve usar cache.

        Returns:
            JSON response com campo 'results' contendo contagens.
        """
        params = self._build_params(search, limit=limit, count=count_field)

        if use_cache and get_config().cache_enabled:
            key = cache_key(Source.FAERS, f"{DRUG_EVENT_ENDPOINT}/count", params)
            store = CacheStore.get_instance()
            cached = store.get(key)
            if cached is not None:
                return cached
        await self._rate_limiter.acquire()
        client = await self._get_client()
        response = await retry_request(
            client,
            "GET",
            DRUG_EVENT_ENDPOINT,
            params=params,
            source_name=Source.FAERS,
        )

        try:
            data: dict[str, Any] = response.json()
        except Exception as exc:
            raise ParseError(Source.FAERS, f"Invalid JSON: {exc}") from exc

        if "error" in data:
            error_msg = data["error"].get("message", "Unknown error")
            if "No matches found" in str(error_msg):
                data = {"results": []}
            else:
                raise SourceUnavailableError(Source.FAERS, str(error_msg))

        if use_cache and get_config().cache_enabled:
            key = cache_key(Source.FAERS, f"{DRUG_EVENT_ENDPOINT}/count", params)
            store = CacheStore.get_instance()
            store.set(key, data, Source.FAERS)

        return data

    async def close(self) -> None:
        """Fecha o client HTTP."""
        if self._client is not None:
            await self._client.aclose()
            self._client = None

    def _build_params(
        self,
        search: str,
        *,
        limit: int = DEFAULT_LIMIT,
        skip: int = 0,
        count: str | None = None,
    ) -> dict[str, str | int | float | bool | None]:
        """Monta parâmetros da request."""
        params: dict[str, str | int | float | bool | None] = {
            "search": search,
            "limit": limit,
        }

        if skip > 0:
            params["skip"] = skip

        if count:
            params["count"] = count

        cfg = get_config()
        if cfg.openfda_api_key:
            params["api_key"] = cfg.openfda_api_key

        return params
