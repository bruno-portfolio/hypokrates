"""HTTP client para MeSH via NCBI E-utilities."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

from hypokrates.cache import CacheStore, cache_key
from hypokrates.config import get_config
from hypokrates.constants import NCBI_EUTILS_BASE_URL, HTTPSettings, Source
from hypokrates.exceptions import ParseError, SourceUnavailableError
from hypokrates.http.rate_limiter import RateLimiter
from hypokrates.http.retry import retry_request
from hypokrates.http.settings import create_client
from hypokrates.pubmed.constants import RATE_WITH_KEY
from hypokrates.vocab.constants import (
    ESEARCH_ENDPOINT,
    ESUMMARY_ENDPOINT,
    MESH_DATABASE,
    TOOL_NAME,
)

if TYPE_CHECKING:
    import httpx

logger = logging.getLogger(__name__)


class MeSHClient:
    """Client HTTP para MeSH via NCBI E-utilities.

    Usa Source.MESH para cache keys (namespace separado do PubMed)
    mas Source.PUBMED para rate limiter (NCBI conta tudo junto).
    """

    def __init__(self) -> None:
        self._client: httpx.AsyncClient | None = None
        cfg = get_config()

        # MeSH compartilha rate com PubMed (mesmo E-utilities)
        rate = HTTPSettings.RATE_LIMITS.get(Source.PUBMED, 180)
        if cfg.ncbi_api_key:
            rate = RATE_WITH_KEY
        self._rate_limiter = RateLimiter.for_source(Source.PUBMED, rate)

    async def _get_client(self) -> httpx.AsyncClient:
        if self._client is None:
            self._client = create_client(base_url=NCBI_EUTILS_BASE_URL)
        return self._client

    async def search(
        self,
        term: str,
        *,
        use_cache: bool = True,
    ) -> dict[str, Any]:
        """ESearch db=mesh — busca termo no MeSH.

        Args:
            term: Termo médico para buscar.
            use_cache: Se deve usar cache.

        Returns:
            JSON response do ESearch.
        """
        params = self._build_search_params(term)

        if use_cache and get_config().cache_enabled:
            key = cache_key(Source.MESH, ESEARCH_ENDPOINT, params)
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
            ESEARCH_ENDPOINT,
            params=params,
            source_name=Source.MESH,
        )

        data = self._parse_response(response)

        if use_cache and get_config().cache_enabled:
            key = cache_key(Source.MESH, ESEARCH_ENDPOINT, params)
            store = CacheStore.get_instance()
            await store.aset(key, data, Source.MESH)

        return data

    async def fetch_descriptor(
        self,
        uid: str,
        *,
        use_cache: bool = True,
    ) -> dict[str, Any]:
        """ESummary db=mesh — busca descriptor por UID.

        Args:
            uid: MeSH UID.
            use_cache: Se deve usar cache.

        Returns:
            JSON response do ESummary.
        """
        params = self._build_summary_params(uid)

        if use_cache and get_config().cache_enabled:
            key = cache_key(Source.MESH, ESUMMARY_ENDPOINT, params)
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
            ESUMMARY_ENDPOINT,
            params=params,
            source_name=Source.MESH,
        )

        data = self._parse_response(response)

        if use_cache and get_config().cache_enabled:
            key = cache_key(Source.MESH, ESUMMARY_ENDPOINT, params)
            store = CacheStore.get_instance()
            await store.aset(key, data, Source.MESH)

        return data

    async def close(self) -> None:
        """Fecha o client HTTP."""
        if self._client is not None:
            await self._client.aclose()
            self._client = None

    def _build_search_params(
        self,
        term: str,
    ) -> dict[str, str | int | float | bool | None]:
        """Monta parâmetros do ESearch db=mesh."""
        params: dict[str, str | int | float | bool | None] = {
            "db": MESH_DATABASE,
            "term": term,
            "retmode": "json",
            "tool": TOOL_NAME,
        }
        self._inject_auth(params)
        return params

    def _build_summary_params(
        self,
        uid: str,
    ) -> dict[str, str | int | float | bool | None]:
        """Monta parâmetros do ESummary db=mesh."""
        params: dict[str, str | int | float | bool | None] = {
            "db": MESH_DATABASE,
            "id": uid,
            "retmode": "json",
            "tool": TOOL_NAME,
        }
        self._inject_auth(params)
        return params

    @staticmethod
    def _inject_auth(params: dict[str, str | int | float | bool | None]) -> None:
        """Injeta credenciais NCBI nos parâmetros."""
        cfg = get_config()
        if cfg.ncbi_email:
            params["email"] = cfg.ncbi_email
        if cfg.ncbi_api_key:
            params["api_key"] = cfg.ncbi_api_key

    @staticmethod
    def _parse_response(response: httpx.Response) -> dict[str, Any]:
        """Parseia JSON response com tratamento de erro."""
        try:
            data: dict[str, Any] = response.json()
        except Exception as exc:
            raise ParseError(Source.MESH, f"Invalid JSON: {exc}") from exc

        if "error" in data:
            raise SourceUnavailableError(Source.MESH, str(data["error"]))

        esearch = data.get("esearchresult", {})
        if isinstance(esearch, dict) and "ERROR" in esearch:
            raise SourceUnavailableError(Source.MESH, str(esearch["ERROR"]))

        return data
