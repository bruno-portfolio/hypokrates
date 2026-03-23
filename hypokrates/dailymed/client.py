"""HTTP client para DailyMed API (bulas FDA / SPL)."""

from __future__ import annotations

import logging
from typing import Any

from hypokrates.constants import DAILYMED_BASE_URL, HTTPSettings, Source
from hypokrates.http.base_client import BaseClient, ParamsType
from hypokrates.http.retry import retry_request

from .constants import SPL_ENDPOINT, SPLS_ENDPOINT

logger = logging.getLogger(__name__)


class DailyMedClient(BaseClient):
    """Client HTTP para a API DailyMed.

    Gerencia rate limiting, retry, e cache transparente.
    """

    def __init__(self) -> None:
        super().__init__(
            source=Source.DAILYMED,
            base_url=DAILYMED_BASE_URL,
            rate=HTTPSettings.RATE_LIMITS.get(Source.DAILYMED, 60),
        )

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
        params: ParamsType = {
            "drug_name": drug_name,
            "pagesize": 100,
        }
        return await self._cached_get(SPLS_ENDPOINT, params, use_cache=use_cache)

    async def fetch_spl_xml(
        self,
        set_id: str,
        *,
        use_cache: bool = True,
    ) -> str:
        """Busca XML completo de um SPL por SET ID."""
        endpoint = f"{SPL_ENDPOINT}/{set_id}.xml"
        cache_params: ParamsType = {"set_id": set_id}

        key, cached = await self._cache_lookup(endpoint, cache_params, use_cache=use_cache)
        if cached is not None:
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
        await self._cache_store(key, {"xml": xml_text})
        return xml_text
