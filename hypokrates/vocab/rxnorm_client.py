"""HTTP client para RxNorm API (normalização de drogas)."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

from hypokrates.cache import CacheStore, cache_key
from hypokrates.config import get_config
from hypokrates.constants import RXNORM_BASE_URL, HTTPSettings, Source
from hypokrates.exceptions import ParseError, SourceUnavailableError
from hypokrates.http.rate_limiter import RateLimiter
from hypokrates.http.retry import retry_request
from hypokrates.http.settings import create_client
from hypokrates.vocab.constants import RXNORM_DRUGS_ENDPOINT

if TYPE_CHECKING:
    import httpx

logger = logging.getLogger(__name__)


class RxNormClient:
    """Client HTTP para a API RxNorm.

    Gerencia rate limiting, retry, e cache transparente.
    """

    def __init__(self) -> None:
        self._client: httpx.AsyncClient | None = None
        rate = HTTPSettings.RATE_LIMITS.get(Source.RXNORM, 120)
        self._rate_limiter = RateLimiter.for_source(Source.RXNORM, rate)

    async def _get_client(self) -> httpx.AsyncClient:
        if self._client is None:
            self._client = create_client(base_url=RXNORM_BASE_URL)
        return self._client

    async def search(
        self,
        name: str,
        *,
        use_cache: bool = True,
    ) -> dict[str, Any]:
        """Busca droga no RxNorm por nome.

        Args:
            name: Nome da droga (brand ou genérico).
            use_cache: Se deve usar cache.

        Returns:
            JSON response do RxNorm /drugs.json.
        """
        params: dict[str, str | int | float | bool | None] = {"name": name}

        if use_cache and get_config().cache_enabled:
            key = cache_key(Source.RXNORM, RXNORM_DRUGS_ENDPOINT, params)
            store = CacheStore.get_instance()
            cached = await store.aget(key)
            if cached is not None:
                logger.debug("Cache hit: %s", key)
                return cached

        await self._rate_limiter.acquire()
        client = await self._get_client()
        response = await retry_request(
            client,
            "GET",
            RXNORM_DRUGS_ENDPOINT,
            params=params,
            source_name=Source.RXNORM,
        )

        data = self._parse_response(response)

        if use_cache and get_config().cache_enabled:
            key = cache_key(Source.RXNORM, RXNORM_DRUGS_ENDPOINT, params)
            store = CacheStore.get_instance()
            await store.aset(key, data, Source.RXNORM)

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
            raise ParseError(Source.RXNORM, f"Invalid JSON: {exc}") from exc

        if "drugGroup" not in data:
            raise SourceUnavailableError(Source.RXNORM, "Response missing 'drugGroup' field")

        return data
