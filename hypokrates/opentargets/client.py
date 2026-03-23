"""HTTP client para OpenTargets GraphQL API."""

from __future__ import annotations

import hashlib
import json
import logging
from typing import TYPE_CHECKING, Any

from hypokrates.constants import HTTPSettings, Source
from hypokrates.exceptions import ParseError
from hypokrates.http.base_client import BaseClient, ParamsType
from hypokrates.http.retry import retry_request

if TYPE_CHECKING:
    import httpx

from .constants import GRAPHQL_URL

logger = logging.getLogger(__name__)


class OpenTargetsClient(BaseClient):
    """Client HTTP para a API GraphQL do OpenTargets.

    Usa POST com JSON body (não GET com params como os outros clients).
    Cache key inclui hash da query+variables.
    """

    def __init__(self) -> None:
        super().__init__(
            source=Source.OPENTARGETS,
            base_url="",
            rate=HTTPSettings.RATE_LIMITS.get(Source.OPENTARGETS, 30),
        )

    async def query(
        self,
        graphql_query: str,
        variables: dict[str, str],
        *,
        use_cache: bool = True,
    ) -> dict[str, Any]:
        """Executa query GraphQL no OpenTargets."""
        cache_params = self._build_cache_params(graphql_query, variables)
        key, cached = await self._cache_lookup("graphql", cache_params, use_cache=use_cache)
        if cached is not None:
            return cached

        await self._rate_limiter.acquire()
        client = await self._get_client()
        body = {"query": graphql_query, "variables": variables}
        response = await retry_request(
            client,
            "POST",
            GRAPHQL_URL,
            json_body=body,
            source_name=Source.OPENTARGETS,
        )

        data = self._parse_response(response)
        await self._cache_store(key, data)
        return data

    @staticmethod
    def _build_cache_params(
        query: str,
        variables: dict[str, str],
    ) -> ParamsType:
        """Gera params para cache key baseado em query+variables."""
        payload = json.dumps({"q": query.strip(), "v": variables}, sort_keys=True)
        query_hash = hashlib.sha256(payload.encode()).hexdigest()[:16]
        return {"query_hash": query_hash}

    def _parse_response(self, response: httpx.Response) -> dict[str, Any]:
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
