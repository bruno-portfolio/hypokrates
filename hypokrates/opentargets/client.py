"""HTTP client para OpenTargets GraphQL API."""

from __future__ import annotations

import asyncio
import hashlib
import json
import logging
from typing import TYPE_CHECKING, Any

from hypokrates.cache import CacheStore, cache_key
from hypokrates.config import get_config
from hypokrates.constants import HTTPSettings, Source
from hypokrates.exceptions import NetworkError, ParseError, RateLimitError
from hypokrates.http.rate_limiter import RateLimiter
from hypokrates.http.settings import create_client

from .constants import GRAPHQL_URL

if TYPE_CHECKING:
    import httpx

logger = logging.getLogger(__name__)

_RETRYABLE_STATUS = {429, 500, 502, 503, 504}


class OpenTargetsClient:
    """Client HTTP para a API GraphQL do OpenTargets.

    Usa POST com JSON body (não GET com params como os outros clients).
    Cache key inclui hash da query+variables.
    Inclui retry com backoff para erros transientes.
    """

    def __init__(self) -> None:
        self._client: httpx.AsyncClient | None = None
        rate = HTTPSettings.RATE_LIMITS.get(Source.OPENTARGETS, 30)
        self._rate_limiter = RateLimiter.for_source(Source.OPENTARGETS, rate)

    async def _get_client(self) -> httpx.AsyncClient:
        if self._client is None:
            self._client = create_client()
        return self._client

    async def query(
        self,
        graphql_query: str,
        variables: dict[str, str],
        *,
        use_cache: bool = True,
    ) -> dict[str, Any]:
        """Executa query GraphQL no OpenTargets.

        Args:
            graphql_query: Query GraphQL.
            variables: Variáveis da query.
            use_cache: Se deve usar cache.

        Returns:
            JSON response (data field).
        """
        should_cache = use_cache and get_config().cache_enabled
        cache_params = self._build_cache_params(graphql_query, variables)
        key = cache_key(Source.OPENTARGETS, "graphql", cache_params) if should_cache else ""

        if should_cache:
            store = CacheStore.get_instance()
            cached = store.get(key)
            if cached is not None:
                logger.debug("Cache hit: %s", key)
                return cached

        await self._rate_limiter.acquire()
        client = await self._get_client()

        body = {"query": graphql_query, "variables": variables}
        response = await self._post_with_retry(client, body)

        data = self._parse_response(response)

        if should_cache:
            store = CacheStore.get_instance()
            store.set(key, data, Source.OPENTARGETS)

        return data

    async def _post_with_retry(
        self,
        client: httpx.AsyncClient,
        body: dict[str, Any],
    ) -> httpx.Response:
        """POST com retry e backoff para erros transientes."""
        import httpx as httpx_mod

        retries = HTTPSettings.MAX_RETRIES
        for attempt in range(retries + 1):
            try:
                response = await client.post(GRAPHQL_URL, json=body)
            except (httpx_mod.TimeoutException, httpx_mod.ConnectError) as exc:
                if attempt < retries:
                    wait = HTTPSettings.BACKOFF_BASE * (HTTPSettings.BACKOFF_FACTOR**attempt)
                    logger.warning(
                        "OpenTargets %s (attempt %d/%d, wait %.1fs)",
                        type(exc).__name__,
                        attempt + 1,
                        retries + 1,
                        wait,
                    )
                    await asyncio.sleep(wait)
                    continue
                raise NetworkError(GRAPHQL_URL, str(exc)) from exc

            if response.status_code == 429:
                if attempt < retries:
                    retry_after = response.headers.get("Retry-After")
                    wait = (
                        float(retry_after)
                        if retry_after
                        else HTTPSettings.BACKOFF_BASE * (HTTPSettings.BACKOFF_FACTOR**attempt)
                    )
                    logger.warning(
                        "OpenTargets rate limit (attempt %d/%d, wait %.1fs)",
                        attempt + 1,
                        retries + 1,
                        wait,
                    )
                    await asyncio.sleep(wait)
                    continue
                raise RateLimitError(Source.OPENTARGETS)

            if response.status_code in _RETRYABLE_STATUS and attempt < retries:
                wait = HTTPSettings.BACKOFF_BASE * (HTTPSettings.BACKOFF_FACTOR**attempt)
                logger.warning(
                    "OpenTargets HTTP %d (attempt %d/%d, wait %.1fs)",
                    response.status_code,
                    attempt + 1,
                    retries + 1,
                    wait,
                )
                await asyncio.sleep(wait)
                continue

            if response.status_code >= 400:
                response.raise_for_status()

            return response

        raise NetworkError(GRAPHQL_URL, "Retry exhausted for OpenTargets")

    async def close(self) -> None:
        """Fecha o client HTTP."""
        if self._client is not None:
            await self._client.aclose()
            self._client = None

    @staticmethod
    def _build_cache_params(
        query: str,
        variables: dict[str, str],
    ) -> dict[str, str | int | float | bool | None]:
        """Gera params para cache key baseado em query+variables."""
        payload = json.dumps({"q": query.strip(), "v": variables}, sort_keys=True)
        query_hash = hashlib.sha256(payload.encode()).hexdigest()[:16]
        return {"query_hash": query_hash}

    @staticmethod
    def _parse_response(response: httpx.Response) -> dict[str, Any]:
        """Parseia JSON response GraphQL."""
        try:
            raw: dict[str, Any] = response.json()
        except Exception as exc:
            raise ParseError(Source.OPENTARGETS, f"Invalid JSON: {exc}") from exc

        if "errors" in raw:
            errors = raw["errors"]
            msg = "; ".join(e.get("message", str(e)) for e in errors)
            raise ParseError(Source.OPENTARGETS, f"GraphQL errors: {msg}")

        data: dict[str, Any] = raw.get("data") or {}
        return data
