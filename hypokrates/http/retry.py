"""Retry com exponential backoff e suporte a Retry-After."""

from __future__ import annotations

import asyncio
import logging
from typing import Any

import httpx

from hypokrates.constants import HTTPSettings, ParamsType
from hypokrates.exceptions import NetworkError, RateLimitError, SourceUnavailableError

logger = logging.getLogger(__name__)

_RETRYABLE_STATUS = {500, 502, 503, 504}
_PASSTHROUGH_STATUS = {404}


async def retry_request(
    client: httpx.AsyncClient,
    method: str,
    url: str,
    *,
    params: ParamsType | None = None,
    headers: dict[str, str] | None = None,
    json_body: dict[str, Any] | None = None,
    max_retries: int | None = None,
    source_name: str = "unknown",
) -> httpx.Response:
    """Executa request HTTP com retry e backoff exponencial.

    Respeita header ``Retry-After`` quando presente (429/503).
    """
    retries = max_retries if max_retries is not None else HTTPSettings.MAX_RETRIES
    last_error: Exception | None = None

    for attempt in range(retries + 1):
        try:
            response = await client.request(
                method,
                url,
                params=params,
                headers=headers,
                json=json_body,
            )

            if response.status_code == 429:
                retry_after = _parse_retry_after(response)
                if attempt < retries:
                    wait = retry_after or calculate_backoff(attempt)
                    logger.warning(
                        "Rate limit %s (attempt %d/%d, wait %.1fs)",
                        source_name,
                        attempt + 1,
                        retries + 1,
                        wait,
                    )
                    await asyncio.sleep(wait)
                    continue
                raise RateLimitError(source_name, retry_after)

            if response.status_code in _RETRYABLE_STATUS and attempt < retries:
                wait = calculate_backoff(attempt)
                logger.warning(
                    "HTTP %d from %s (attempt %d/%d, wait %.1fs)",
                    response.status_code,
                    source_name,
                    attempt + 1,
                    retries + 1,
                    wait,
                )
                await asyncio.sleep(wait)
                continue

            if response.status_code in _PASSTHROUGH_STATUS:
                return response

            if response.status_code >= 400:
                response.raise_for_status()

            return response

        except httpx.TimeoutException as exc:
            last_error = exc
            if attempt < retries:
                wait = calculate_backoff(attempt)
                logger.warning(
                    "Timeout %s (attempt %d/%d, wait %.1fs)",
                    source_name,
                    attempt + 1,
                    retries + 1,
                    wait,
                )
                await asyncio.sleep(wait)
                continue

        except httpx.ConnectError as exc:
            last_error = exc
            if attempt < retries:
                wait = calculate_backoff(attempt)
                logger.warning(
                    "Connection error %s (attempt %d/%d, wait %.1fs)",
                    source_name,
                    attempt + 1,
                    retries + 1,
                    wait,
                )
                await asyncio.sleep(wait)
                continue

        except httpx.HTTPStatusError as exc:
            if exc.response.status_code >= 500:
                raise SourceUnavailableError(source_name, str(exc)) from exc
            raise NetworkError(url, str(exc)) from exc

    if last_error is not None:
        raise NetworkError(url, str(last_error)) from last_error

    msg = f"Retry exhausted for {source_name}"
    raise NetworkError(url, msg)


def calculate_backoff(attempt: int) -> float:
    """Calcula delay com exponential backoff."""
    delay = HTTPSettings.BACKOFF_BASE * (HTTPSettings.BACKOFF_FACTOR**attempt)
    return min(delay, HTTPSettings.BACKOFF_MAX)


def _parse_retry_after(response: httpx.Response) -> float | None:
    """Parseia header Retry-After (segundos)."""
    value = response.headers.get("Retry-After")
    if value is None:
        return None
    try:
        return float(value)
    except ValueError:
        return None
