"""HTTP client para OpenFDA FAERS API."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

from hypokrates.cache import CacheStore, cache_key
from hypokrates.config import get_config
from hypokrates.constants import OPENFDA_BASE_URL, Source
from hypokrates.exceptions import ParseError, SourceUnavailableError
from hypokrates.faers.constants import DEFAULT_COUNT_LIMIT, DEFAULT_LIMIT, DRUG_EVENT_ENDPOINT
from hypokrates.http.base_client import BaseClient, ParamsType
from hypokrates.http.retry import retry_request

if TYPE_CHECKING:
    import httpx

logger = logging.getLogger(__name__)


class FAERSClient(BaseClient):
    """Client HTTP para a API OpenFDA drug/event.

    Gerencia rate limiting, retry, e cache transparente.
    """

    def __init__(self) -> None:
        cfg = get_config()
        rate = 240 if cfg.openfda_api_key else 40
        super().__init__(
            source=Source.FAERS,
            base_url=OPENFDA_BASE_URL,
            rate=rate,
        )

    async def fetch(
        self,
        search: str,
        *,
        limit: int = DEFAULT_LIMIT,
        skip: int = 0,
        use_cache: bool = True,
    ) -> dict[str, Any]:
        """Busca reports no OpenFDA.

        Args:
            search: Query string OpenFDA (e.g., 'patient.drug.openfda.generic_name:"propofol"')
            limit: Máximo de resultados por página.
            skip: Offset para paginação.
            use_cache: Se deve usar cache.

        Returns:
            JSON response completo do OpenFDA.
        """
        params = self._build_params(search, limit=limit, skip=skip)
        return await self._cached_get(DRUG_EVENT_ENDPOINT, params, use_cache=use_cache)

    async def fetch_count(
        self,
        search: str,
        count_field: str,
        *,
        limit: int = DEFAULT_COUNT_LIMIT,
        use_cache: bool = True,
    ) -> dict[str, Any]:
        """Busca contagens agregadas no OpenFDA.

        Args:
            search: Query string OpenFDA.
            count_field: Campo para agregar (e.g., 'patient.reaction.reactionmeddrapt.exact').
            limit: Máximo de buckets retornados.
            use_cache: Se deve usar cache.

        Returns:
            JSON response com campo 'results' contendo contagens.
        """
        params = self._build_params(search, limit=limit, count=count_field)
        return await self._cached_get(
            DRUG_EVENT_ENDPOINT,
            params,
            use_cache=use_cache,
            cache_suffix="/count",
        )

    async def fetch_total(
        self,
        search: str,
        *,
        use_cache: bool = True,
    ) -> int:
        """Retorna total de reports que matcham uma query.

        Nota: o total é um snapshot — o FAERS atualiza trimestralmente.
        Com cache TTL=24h, o valor pode ficar levemente desatualizado
        entre updates, mas a diferença é marginal para cálculos de
        desproporcionalidade.

        Args:
            search: Query string OpenFDA.
            use_cache: Se deve usar cache.

        Returns:
            Total de reports (int). 0 se nenhum match.
        """
        params = self._build_params(search, limit=1)

        should_cache = use_cache and get_config().cache_enabled
        ep = f"{DRUG_EVENT_ENDPOINT}/total"
        key = cache_key(Source.FAERS, ep, params) if should_cache else ""

        if should_cache:
            store = CacheStore.get_instance()
            cached = await store.aget(key)
            if cached is not None:
                logger.debug("Cache hit (total): %s", key)
                raw_total: Any = cached.get("total", 0)
                return int(raw_total)

        await self._rate_limiter.acquire()
        client = await self._get_client()
        response = await retry_request(
            client,
            "GET",
            DRUG_EVENT_ENDPOINT,
            params=params,
            source_name=Source.FAERS,
        )

        try:
            data: dict[str, Any] = response.json()
        except Exception as exc:
            raise ParseError(Source.FAERS, f"Invalid JSON: {exc}") from exc

        if "error" in data:
            error_msg = data["error"].get("message", "Unknown error")
            if "No matches found" in str(error_msg):
                total = 0
            else:
                raise SourceUnavailableError(Source.FAERS, str(error_msg))
        else:
            try:
                meta = data.get("meta", {})
                results_meta = meta.get("results", {})
                total = int(results_meta.get("total", 0))
            except (ValueError, TypeError):
                total = 0

        if should_cache:
            store = CacheStore.get_instance()
            await store.aset(key, {"total": total}, Source.FAERS)

        return total

    def _parse_response(self, response: httpx.Response) -> dict[str, Any]:
        """Parseia JSON response com tratamento de 'No matches found'."""
        try:
            data: dict[str, Any] = response.json()
        except Exception as exc:
            raise ParseError(Source.FAERS, f"Invalid JSON: {exc}") from exc

        if "error" in data:
            error_msg = data["error"].get("message", "Unknown error")
            if "No matches found" in str(error_msg):
                data = {"meta": {"results": {"total": 0}}, "results": []}
            else:
                raise SourceUnavailableError(Source.FAERS, str(error_msg))

        return data

    def _build_params(
        self,
        search: str,
        *,
        limit: int = DEFAULT_LIMIT,
        skip: int = 0,
        count: str | None = None,
    ) -> ParamsType:
        """Monta parâmetros da request."""
        params: ParamsType = {
            "search": search,
            "limit": limit,
        }

        if skip > 0:
            params["skip"] = skip

        if count:
            params["count"] = count

        cfg = get_config()
        if cfg.openfda_api_key:
            params["api_key"] = cfg.openfda_api_key

        return params
