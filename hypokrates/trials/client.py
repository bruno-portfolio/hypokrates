"""HTTP client para ClinicalTrials.gov v2 API.

Usa curl_cffi (quando disponível) para bypass de TLS fingerprinting
do Cloudflare. Fallback para httpx com aviso.
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any

from hypokrates.constants import TRIALS_BASE_URL, HTTPSettings, Source
from hypokrates.exceptions import NetworkError, ParseError, RateLimitError
from hypokrates.http.base_client import BaseClient, ParamsType
from hypokrates.http.retry import calculate_backoff, retry_request

from .constants import STUDIES_ENDPOINT

try:
    from curl_cffi.requests import AsyncSession as CffiSession

    _HAS_CURL_CFFI = True
except ImportError:
    _HAS_CURL_CFFI = False

logger = logging.getLogger(__name__)
_WARNED_NO_CURL_CFFI = False


class TrialsClient(BaseClient):
    """Client HTTP para ClinicalTrials.gov v2 API.

    Gerencia rate limiting, retry, e cache transparente.
    Usa curl_cffi para contornar TLS fingerprinting do Cloudflare.
    """

    def __init__(self) -> None:
        super().__init__(
            source=Source.TRIALS,
            base_url=TRIALS_BASE_URL,
            rate=HTTPSettings.RATE_LIMITS.get(Source.TRIALS, 50),
        )
        self._cffi_session: Any | None = None

    async def search(
        self,
        drug: str,
        event: str,
        *,
        page_size: int = 10,
        use_cache: bool = True,
    ) -> dict[str, Any]:
        """Busca trials clínicos por droga e evento."""
        params: ParamsType = {
            "query.intr": drug,
            "query.cond": event,
            "pageSize": page_size,
        }

        key, cached = await self._cache_lookup(STUDIES_ENDPOINT, params, use_cache=use_cache)
        if cached is not None:
            return cached

        await self._rate_limiter.acquire()
        data = await self._fetch(params)
        await self._cache_store(key, data)
        return data

    async def _fetch(self, params: ParamsType) -> dict[str, Any]:
        """Executa o request HTTP, usando curl_cffi ou httpx."""
        if _HAS_CURL_CFFI:
            return await self._fetch_cffi(params)
        return await self._fetch_httpx(params)

    async def _fetch_cffi(
        self,
        params: ParamsType,
    ) -> dict[str, Any]:
        """Fetch via curl_cffi com retry básico."""
        url = f"{TRIALS_BASE_URL}{STUDIES_ENDPOINT}"
        str_params = {k: str(v) for k, v in params.items() if v is not None}
        max_retries = HTTPSettings.MAX_RETRIES
        last_error: Exception | None = None

        for attempt in range(max_retries + 1):
            try:
                if self._cffi_session is None:
                    self._cffi_session = CffiSession(
                        impersonate="chrome",
                        timeout=HTTPSettings.TIMEOUT,
                    )
                response = await self._cffi_session.get(url, params=str_params)
                status: int = response.status_code

                if status == 429:
                    if attempt < max_retries:
                        wait = calculate_backoff(attempt)
                        logger.warning(
                            "Rate limit %s (attempt %d/%d, wait %.1fs)",
                            Source.TRIALS,
                            attempt + 1,
                            max_retries + 1,
                            wait,
                        )
                        await asyncio.sleep(wait)
                        continue
                    raise RateLimitError(Source.TRIALS, None)

                if status >= 500 and attempt < max_retries:
                    wait = calculate_backoff(attempt)
                    logger.warning(
                        "HTTP %d from %s (attempt %d/%d, wait %.1fs)",
                        status,
                        Source.TRIALS,
                        attempt + 1,
                        max_retries + 1,
                        wait,
                    )
                    await asyncio.sleep(wait)
                    continue

                if status >= 400:
                    raise NetworkError(url, f"HTTP {status} from {Source.TRIALS}")

                return self._parse_json(response.text)

            except (OSError, ConnectionError) as exc:
                last_error = exc
                if attempt < max_retries:
                    wait = calculate_backoff(attempt)
                    logger.warning(
                        "Connection error %s (attempt %d/%d, wait %.1fs)",
                        Source.TRIALS,
                        attempt + 1,
                        max_retries + 1,
                        wait,
                    )
                    await asyncio.sleep(wait)
                    continue

        if last_error is not None:
            raise NetworkError(url, str(last_error)) from last_error
        msg = f"Retry exhausted for {Source.TRIALS}"
        raise NetworkError(url, msg)

    async def _fetch_httpx(
        self,
        params: ParamsType,
    ) -> dict[str, Any]:
        """Fetch via httpx (fallback — pode falhar com 403 no Cloudflare)."""
        global _WARNED_NO_CURL_CFFI
        if not _WARNED_NO_CURL_CFFI:
            logger.warning(
                "curl_cffi não disponível — ClinicalTrials.gov pode retornar 403. "
                "Instale com: pip install curl_cffi"
            )
            _WARNED_NO_CURL_CFFI = True

        client = await self._get_client()
        response = await retry_request(
            client,
            "GET",
            STUDIES_ENDPOINT,
            params=params,
            source_name=Source.TRIALS,
        )
        return self._parse_response(response)

    async def close(self) -> None:
        """Fecha o client HTTP e a sessão curl_cffi."""
        await super().close()
        if self._cffi_session is not None:
            await self._cffi_session.close()
            self._cffi_session = None

    @staticmethod
    def _parse_json(text: str) -> dict[str, Any]:
        """Parseia JSON text com tratamento de erro."""
        import json

        try:
            data: dict[str, Any] = json.loads(text)
        except Exception as exc:
            raise ParseError(Source.TRIALS, f"Invalid JSON: {exc}") from exc
        return data
