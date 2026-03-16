"""HTTP client para MeSH via NCBI E-utilities."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from hypokrates.config import get_config
from hypokrates.constants import NCBI_EUTILS_BASE_URL, HTTPSettings, Source
from hypokrates.exceptions import ParseError, SourceUnavailableError
from hypokrates.http.auth import inject_ncbi_auth
from hypokrates.http.base_client import BaseClient, ParamsType
from hypokrates.pubmed.constants import RATE_WITH_KEY
from hypokrates.vocab.constants import (
    ESEARCH_ENDPOINT,
    ESUMMARY_ENDPOINT,
    MESH_DATABASE,
    TOOL_NAME,
)

if TYPE_CHECKING:
    import httpx


class MeSHClient(BaseClient):
    """Client HTTP para MeSH via NCBI E-utilities.

    Usa Source.MESH para cache keys (namespace separado do PubMed)
    mas Source.PUBMED para rate limiter (NCBI conta tudo junto).
    """

    def __init__(self) -> None:
        cfg = get_config()
        rate = HTTPSettings.RATE_LIMITS.get(Source.PUBMED, 180)
        if cfg.ncbi_api_key:
            rate = RATE_WITH_KEY
        super().__init__(
            source=Source.MESH,
            base_url=NCBI_EUTILS_BASE_URL,
            rate=rate,
            rate_source=Source.PUBMED,
        )

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
        return await self._cached_get(ESEARCH_ENDPOINT, params, use_cache=use_cache)

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
        return await self._cached_get(ESUMMARY_ENDPOINT, params, use_cache=use_cache)

    def _build_search_params(
        self,
        term: str,
        *,
        retmax: int = 20,
    ) -> ParamsType:
        """Monta parâmetros do ESearch db=mesh."""
        params: ParamsType = {
            "db": MESH_DATABASE,
            "term": term,
            "retmode": "json",
            "retmax": retmax,
            "tool": TOOL_NAME,
        }
        inject_ncbi_auth(params)
        return params

    def _build_summary_params(
        self,
        uid: str,
    ) -> ParamsType:
        """Monta parâmetros do ESummary db=mesh."""
        params: ParamsType = {
            "db": MESH_DATABASE,
            "id": uid,
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
            raise ParseError(Source.MESH, f"Invalid JSON: {exc}") from exc

        if "error" in data:
            raise SourceUnavailableError(Source.MESH, str(data["error"]))

        esearch = data.get("esearchresult", {})
        if isinstance(esearch, dict) and "ERROR" in esearch:
            raise SourceUnavailableError(Source.MESH, str(esearch["ERROR"]))

        return data
