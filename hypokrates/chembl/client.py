"""HTTP client para ChEMBL REST API."""

from __future__ import annotations

from typing import Any

from hypokrates.http.base_client import BaseClient, ParamsType

from .constants import CHEMBL_BASE_URL, CHEMBL_RATE_PER_MINUTE

_CHEMBL_SOURCE = "chembl"


class ChEMBLClient(BaseClient):
    """Client HTTP para a API REST do ChEMBL.

    API pública, sem autenticação, rate limit generoso.
    """

    def __init__(self) -> None:
        super().__init__(
            source=_CHEMBL_SOURCE,
            base_url=CHEMBL_BASE_URL,
            rate=CHEMBL_RATE_PER_MINUTE,
        )

    async def get(
        self,
        endpoint: str,
        params: ParamsType | None = None,
        *,
        use_cache: bool = True,
    ) -> dict[str, Any]:
        """GET request com cache e rate limiting.

        Args:
            endpoint: Endpoint relativo (e.g., "/mechanism.json").
            params: Query params.
            use_cache: Se deve usar cache.

        Returns:
            JSON response.
        """
        return await self._cached_get(endpoint, params, use_cache=use_cache)
