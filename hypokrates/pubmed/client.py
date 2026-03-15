"""HTTP client para NCBI E-utilities (PubMed)."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from hypokrates.config import get_config
from hypokrates.constants import NCBI_EUTILS_BASE_URL, HTTPSettings, Source
from hypokrates.exceptions import ParseError, SourceUnavailableError
from hypokrates.http.auth import inject_ncbi_auth
from hypokrates.http.base_client import BaseClient, ParamsType
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


class PubMedClient(BaseClient):
    """Client HTTP para a API NCBI E-utilities (PubMed).

    Gerencia rate limiting, retry, e cache transparente.
    """

    def __init__(self) -> None:
        cfg = get_config()
        rate = HTTPSettings.RATE_LIMITS.get(Source.PUBMED, 180)
        if cfg.ncbi_api_key:
            rate = RATE_WITH_KEY
        super().__init__(
            source=Source.PUBMED,
            base_url=NCBI_EUTILS_BASE_URL,
            rate=rate,
        )

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
        return await self._cached_get(
            ESEARCH_ENDPOINT,
            params,
            use_cache=use_cache,
            cache_suffix="/count",
        )

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
        return await self._cached_get(ESEARCH_ENDPOINT, params, use_cache=use_cache)

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
        return await self._cached_get(ESUMMARY_ENDPOINT, params, use_cache=use_cache)

    def _build_params(
        self,
        term: str,
        *,
        retmax: int | None = None,
        rettype: str | None = None,
    ) -> ParamsType:
        """Monta parâmetros do ESearch."""
        params: ParamsType = {
            "db": DATABASE,
            "term": term,
            "retmode": "json",
            "tool": TOOL_NAME,
        }
        if retmax is not None:
            params["retmax"] = retmax
        if rettype is not None:
            params["rettype"] = rettype
        inject_ncbi_auth(params)
        return params

    def _build_summary_params(
        self,
        ids: str,
    ) -> ParamsType:
        """Monta parâmetros do ESummary."""
        params: ParamsType = {
            "db": DATABASE,
            "id": ids,
            "retmode": "json",
            "tool": TOOL_NAME,
        }
        inject_ncbi_auth(params)
        return params

    def _parse_response(self, response: httpx.Response) -> dict[str, Any]:
        """Parseia JSON response com tratamento de erro NCBI."""
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
