"""HTTP client para DailyMed API (bulas FDA / SPL)."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

from hypokrates.cache import CacheStore, cache_key
from hypokrates.config import get_config
from hypokrates.constants import DAILYMED_BASE_URL, HTTPSettings, Source
from hypokrates.exceptions import ParseError
from hypokrates.http.rate_limiter import RateLimiter
from hypokrates.http.retry import retry_request
from hypokrates.http.settings import create_client

from .constants import SPL_ENDPOINT, SPLS_ENDPOINT

if TYPE_CHECKING:
    import httpx

logger = logging.getLogger(__name__)


class DailyMedClient:
    """Client HTTP para a API DailyMed.

    Gerencia rate limiting, retry, e cache transparente.
    """

    def __init__(self) -> None:
        self._client: httpx.AsyncClient | None = None
        rate = HTTPSettings.RATE_LIMITS.get(Source.DAILYMED, 60)
        self._rate_limiter = RateLimiter.for_source(Source.DAILYMED, rate)

    async def _get_client(self) -> httpx.AsyncClient:
        if self._client is None:
            self._client = create_client(base_url=DAILYMED_BASE_URL)
        return self._client

    async def search_spls(
        self,
        drug_name: str,
        *,
        use_cache: bool = True,
    ) -> dict[str, Any]:
        """Busca SPLs (bulas) por nome de droga.

        Args:
            drug_name: Nome da droga.
            use_cache: Se deve usar cache.

        Returns:
            JSON response de /spls.json.
        """
        params: dict[str, str | int | float | bool | None] = {
            "drug_name": drug_name,
            "pagesize": 1,
        }

        should_cache = use_cache and get_config().cache_enabled
        key = cache_key(Source.DAILYMED, SPLS_ENDPOINT, params) if should_cache else ""

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
            SPLS_ENDPOINT,
            params=params,
            source_name=Source.DAILYMED,
        )

        data = self._parse_json_response(response)

        if should_cache:
            store = CacheStore.get_instance()
            await store.aset(key, data, Source.DAILYMED)

        return data

    async def fetch_spl_xml(
        self,
        set_id: str,
        *,
        use_cache: bool = True,
    ) -> str:
        """Busca XML completo de um SPL por SET ID.

        Args:
            set_id: UUID do SPL (SET ID).
            use_cache: Se deve usar cache.

        Returns:
            XML text do SPL.
        """
        endpoint = f"{SPL_ENDPOINT}/{set_id}.xml"
        cache_params: dict[str, str | int | float | bool | None] = {"set_id": set_id}

        should_cache = use_cache and get_config().cache_enabled
        key = cache_key(Source.DAILYMED, endpoint, cache_params) if should_cache else ""

        if should_cache:
            store = CacheStore.get_instance()
            cached = await store.aget(key)
            if cached is not None:
                logger.debug("Cache hit: %s", key)
                return str(cached.get("xml", ""))

        await self._rate_limiter.acquire()
        client = await self._get_client()
        response = await retry_request(
            client,
            "GET",
            endpoint,
            source_name=Source.DAILYMED,
        )

        xml_text = response.text

        if should_cache:
            store = CacheStore.get_instance()
            await store.aset(key, {"xml": xml_text}, Source.DAILYMED)

        return xml_text

    async def close(self) -> None:
        """Fecha o client HTTP."""
        if self._client is not None:
            await self._client.aclose()
            self._client = None

    @staticmethod
    def _parse_json_response(response: httpx.Response) -> dict[str, Any]:
        """Parseia JSON response com tratamento de erro."""
        try:
            data: dict[str, Any] = response.json()
        except Exception as exc:
            raise ParseError(Source.DAILYMED, f"Invalid JSON: {exc}") from exc
        return data
