"""HTTP client para RxNorm API (normalização de drogas)."""

from __future__ import annotations

from typing import Any

from hypokrates.constants import RXNORM_BASE_URL, HTTPSettings, Source
from hypokrates.exceptions import SourceUnavailableError
from hypokrates.http.base_client import BaseClient, ParamsType
from hypokrates.vocab.constants import (
    RXNORM_ALLRELATED_ENDPOINT,
    RXNORM_DRUGS_ENDPOINT,
    RXNORM_RXCUI_ENDPOINT,
)


class RxNormClient(BaseClient):
    """Client HTTP para a API RxNorm.

    Gerencia rate limiting, retry, e cache transparente.
    """

    def __init__(self) -> None:
        super().__init__(
            source=Source.RXNORM,
            base_url=RXNORM_BASE_URL,
            rate=HTTPSettings.RATE_LIMITS.get(Source.RXNORM, 120),
        )

    async def search(
        self,
        name: str,
        *,
        use_cache: bool = True,
    ) -> dict[str, Any]:
        """Busca droga no RxNorm por nome.

        Args:
            name: Nome da droga (brand ou genérico).
            use_cache: Se deve usar cache.

        Returns:
            JSON response do RxNorm /drugs.json.
        """
        params: ParamsType = {"name": name}
        data = await self._cached_get(RXNORM_DRUGS_ENDPOINT, params, use_cache=use_cache)

        if "drugGroup" not in data:
            raise SourceUnavailableError(Source.RXNORM, "Response missing 'drugGroup' field")

        return data

    async def search_by_name(
        self,
        name: str,
        *,
        use_cache: bool = True,
    ) -> dict[str, Any]:
        """Busca RXCUI por nome exato via /rxcui.json.

        Args:
            name: Nome da droga.
            use_cache: Se deve usar cache.

        Returns:
            JSON response do RxNorm /rxcui.json.
        """
        params: ParamsType = {"name": name}
        return await self._cached_get(RXNORM_RXCUI_ENDPOINT, params, use_cache=use_cache)

    async def fetch_allrelated(
        self,
        rxcui: str,
        *,
        use_cache: bool = True,
    ) -> dict[str, Any]:
        """Busca todos os conceitos relacionados a um RXCUI.

        Args:
            rxcui: RXCUI do medicamento.
            use_cache: Se deve usar cache.

        Returns:
            JSON response do RxNorm /rxcui/{id}/allrelated.json.
        """
        endpoint = RXNORM_ALLRELATED_ENDPOINT.format(rxcui=rxcui)
        return await self._cached_get(endpoint, use_cache=use_cache)
