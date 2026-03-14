"""HTTP client para ClinicalTrials.gov v2 API."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

from hypokrates.cache import CacheStore, cache_key
from hypokrates.config import get_config
from hypokrates.constants import TRIALS_BASE_URL, HTTPSettings, Source
from hypokrates.exceptions import ParseError
from hypokrates.http.rate_limiter import RateLimiter
from hypokrates.http.retry import retry_request
from hypokrates.http.settings import create_client

from .constants import STUDIES_ENDPOINT

if TYPE_CHECKING:
    import httpx

logger = logging.getLogger(__name__)


class TrialsClient:
    """Client HTTP para ClinicalTrials.gov v2 API.

    Gerencia rate limiting, retry, e cache transparente.
    """

    def __init__(self) -> None:
        self._client: httpx.AsyncClient | None = None
        rate = HTTPSettings.RATE_LIMITS.get(Source.TRIALS, 50)
        self._rate_limiter = RateLimiter.for_source(Source.TRIALS, rate)

    async def _get_client(self) -> httpx.AsyncClient:
        if self._client is None:
            self._client = create_client(base_url=TRIALS_BASE_URL)
        return self._client

    async def search(
        self,
        drug: str,
        event: str,
        *,
        page_size: int = 10,
        use_cache: bool = True,
    ) -> dict[str, Any]:
        """Busca trials clínicos por droga e evento.

        Args:
            drug: Nome da droga (intervention).
            event: Termo do evento (condition).
            page_size: Máximo de resultados.
            use_cache: Se deve usar cache.

        Returns:
            JSON response de /studies.
        """
        params: dict[str, str | int | float | bool | None] = {
            "query.intr": drug,
            "query.cond": event,
            "pageSize": page_size,
        }

        should_cache = use_cache and get_config().cache_enabled
        key = cache_key(Source.TRIALS, STUDIES_ENDPOINT, params) if should_cache else ""

        if should_cache:
            store = CacheStore.get_instance()
            cached = store.get(key)
            if cached is not None:
                logger.debug("Cache hit: %s", key)
                return cached

        await self._rate_limiter.acquire()
        client = await self._get_client()
        response = await retry_request(
            client,
            "GET",
            STUDIES_ENDPOINT,
            params=params,
            source_name=Source.TRIALS,
        )

        data = self._parse_response(response)

        if should_cache:
            store = CacheStore.get_instance()
            store.set(key, data, Source.TRIALS)

        return data

    async def close(self) -> None:
        """Fecha o client HTTP."""
        if self._client is not None:
            await self._client.aclose()
            self._client = None

    @staticmethod
    def _parse_response(response: httpx.Response) -> dict[str, Any]:
        """Parseia JSON response com tratamento de erro."""
        try:
            data: dict[str, Any] = response.json()
        except Exception as exc:
            raise ParseError(Source.TRIALS, f"Invalid JSON: {exc}") from exc
        return data
