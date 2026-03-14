"""HTTP client para ChEMBL REST API."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

from hypokrates.cache import CacheStore, cache_key
from hypokrates.config import get_config
from hypokrates.exceptions import ParseError
from hypokrates.http.rate_limiter import RateLimiter
from hypokrates.http.retry import retry_request
from hypokrates.http.settings import create_client

from .constants import CHEMBL_BASE_URL, CHEMBL_RATE_PER_MINUTE

if TYPE_CHECKING:
    import httpx

logger = logging.getLogger(__name__)

# Reusa Source.DRUGBANK para cache key (ChEMBL é dado de droga, mesmo domínio)
# mas cria rate limiter próprio
_CHEMBL_SOURCE = "chembl"


class ChEMBLClient:
    """Client HTTP para a API REST do ChEMBL.

    API pública, sem autenticação, rate limit generoso.
    """

    def __init__(self) -> None:
        self._client: httpx.AsyncClient | None = None
        self._rate_limiter = RateLimiter.for_source(_CHEMBL_SOURCE, CHEMBL_RATE_PER_MINUTE)

    async def _get_client(self) -> httpx.AsyncClient:
        if self._client is None:
            self._client = create_client(base_url=CHEMBL_BASE_URL)
        return self._client

    async def get(
        self,
        endpoint: str,
        params: dict[str, str | int | float | bool | None] | None = None,
        *,
        use_cache: bool = True,
    ) -> dict[str, Any]:
        """GET request com cache e rate limiting.

        Args:
            endpoint: Endpoint relativo (e.g., "/mechanism.json").
            params: Query params.
            use_cache: Se deve usar cache.

        Returns:
            JSON response.
        """
        should_cache = use_cache and get_config().cache_enabled
        key = cache_key(_CHEMBL_SOURCE, endpoint, params) if should_cache else ""

        if should_cache:
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
            endpoint,
            params=params,
            source_name=_CHEMBL_SOURCE,
        )

        data = self._parse_response(response)

        if should_cache:
            store = CacheStore.get_instance()
            await store.aset(key, data, _CHEMBL_SOURCE)

        return data

    async def close(self) -> None:
        """Fecha o client HTTP."""
        if self._client is not None:
            await self._client.aclose()
            self._client = None

    @staticmethod
    def _parse_response(response: httpx.Response) -> dict[str, Any]:
        """Parseia JSON response."""
        try:
            data: dict[str, Any] = response.json()
        except Exception as exc:
            raise ParseError(_CHEMBL_SOURCE, f"Invalid JSON: {exc}") from exc
        return data
