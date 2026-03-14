"""HTTP client para NCBI E-utilities (PubMed)."""

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
from hypokrates.pubmed.constants import (
    DATABASE,
    DEFAULT_RETMAX,
    ESEARCH_ENDPOINT,
    ESUMMARY_ENDPOINT,
    RATE_WITH_KEY,
    TOOL_NAME,
)

if TYPE_CHECKING:
    import httpx

logger = logging.getLogger(__name__)


class PubMedClient:
    """Client HTTP para a API NCBI E-utilities (PubMed).

    Gerencia rate limiting, retry, e cache transparente.
    """

    def __init__(self) -> None:
        self._client: httpx.AsyncClient | None = None
        cfg = get_config()

        rate = HTTPSettings.RATE_LIMITS.get(Source.PUBMED, 180)
        if cfg.ncbi_api_key:
            rate = RATE_WITH_KEY
        self._rate_limiter = RateLimiter.for_source(Source.PUBMED, rate)

    async def _get_client(self) -> httpx.AsyncClient:
        if self._client is None:
            self._client = create_client(base_url=NCBI_EUTILS_BASE_URL)
        return self._client

    async def search_count(
        self,
        term: str,
        *,
        use_cache: bool = True,
    ) -> dict[str, Any]:
        """ESearch com rettype=count — retorna apenas contagem.

        Args:
            term: Termo de busca PubMed.
            use_cache: Se deve usar cache.

        Returns:
            JSON response do ESearch.
        """
        params = self._build_params(term, rettype="count")

        if use_cache and get_config().cache_enabled:
            key = cache_key(Source.PUBMED, f"{ESEARCH_ENDPOINT}/count", params)
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
            source_name=Source.PUBMED,
        )

        data = self._parse_response(response)

        if use_cache and get_config().cache_enabled:
            key = cache_key(Source.PUBMED, f"{ESEARCH_ENDPOINT}/count", params)
            store = CacheStore.get_instance()
            await store.aset(key, data, Source.PUBMED)

        return data

    async def search_ids(
        self,
        term: str,
        *,
        retmax: int = DEFAULT_RETMAX,
        use_cache: bool = True,
    ) -> dict[str, Any]:
        """ESearch — retorna PMIDs e contagem total.

        Args:
            term: Termo de busca PubMed.
            retmax: Máximo de PMIDs retornados.
            use_cache: Se deve usar cache.

        Returns:
            JSON response do ESearch com idlist.
        """
        params = self._build_params(term, retmax=retmax)

        if use_cache and get_config().cache_enabled:
            key = cache_key(Source.PUBMED, ESEARCH_ENDPOINT, params)
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
            source_name=Source.PUBMED,
        )

        data = self._parse_response(response)

        if use_cache and get_config().cache_enabled:
            key = cache_key(Source.PUBMED, ESEARCH_ENDPOINT, params)
            store = CacheStore.get_instance()
            await store.aset(key, data, Source.PUBMED)

        return data

    async def fetch_summaries(
        self,
        pmids: list[str],
        *,
        use_cache: bool = True,
    ) -> dict[str, Any]:
        """ESummary — retorna metadados dos artigos.

        Args:
            pmids: Lista de PMIDs.
            use_cache: Se deve usar cache.

        Returns:
            JSON response do ESummary.
        """
        if not pmids:
            return {"result": {"uids": []}}

        ids_str = ",".join(pmids)
        params = self._build_summary_params(ids_str)

        if use_cache and get_config().cache_enabled:
            key = cache_key(Source.PUBMED, ESUMMARY_ENDPOINT, params)
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
            source_name=Source.PUBMED,
        )

        data = self._parse_response(response)

        if use_cache and get_config().cache_enabled:
            key = cache_key(Source.PUBMED, ESUMMARY_ENDPOINT, params)
            store = CacheStore.get_instance()
            await store.aset(key, data, Source.PUBMED)

        return data

    async def close(self) -> None:
        """Fecha o client HTTP."""
        if self._client is not None:
            await self._client.aclose()
            self._client = None

    def _build_params(
        self,
        term: str,
        *,
        retmax: int | None = None,
        rettype: str | None = None,
    ) -> dict[str, str | int | float | bool | None]:
        """Monta parâmetros do ESearch."""
        params: dict[str, str | int | float | bool | None] = {
            "db": DATABASE,
            "term": term,
            "retmode": "json",
            "tool": TOOL_NAME,
        }
        if retmax is not None:
            params["retmax"] = retmax
        if rettype is not None:
            params["rettype"] = rettype
        self._inject_auth(params)
        return params

    def _build_summary_params(
        self,
        ids: str,
    ) -> dict[str, str | int | float | bool | None]:
        """Monta parâmetros do ESummary."""
        params: dict[str, str | int | float | bool | None] = {
            "db": DATABASE,
            "id": ids,
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
            raise ParseError(Source.PUBMED, f"Invalid JSON: {exc}") from exc

        # NCBI retorna erros como campo "error" ou "esearchresult.ERROR"
        if "error" in data:
            raise SourceUnavailableError(Source.PUBMED, str(data["error"]))

        esearch = data.get("esearchresult", {})
        if "ERROR" in esearch:
            raise SourceUnavailableError(Source.PUBMED, str(esearch["ERROR"]))

        return data
