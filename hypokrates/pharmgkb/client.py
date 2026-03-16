"""HTTP client para PharmGKB REST API."""

from __future__ import annotations

from typing import Any

from hypokrates.http.base_client import BaseClient, ParamsType

from .constants import PHARMGKB_BASE_URL, PHARMGKB_RATE_PER_MINUTE

_PHARMGKB_SOURCE = "pharmgkb"


class PharmGKBClient(BaseClient):
    """Client HTTP para a API REST do PharmGKB.

    API pública, sem autenticação.
    """

    def __init__(self) -> None:
        super().__init__(
            source=_PHARMGKB_SOURCE,
            base_url=PHARMGKB_BASE_URL,
            rate=PHARMGKB_RATE_PER_MINUTE,
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
            endpoint: Endpoint relativo (e.g., "/chemical").
            params: Query params.
            use_cache: Se deve usar cache.

        Returns:
            JSON response.
        """
        return await self._cached_get(endpoint, params, use_cache=use_cache)
