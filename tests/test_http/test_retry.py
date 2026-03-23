"""Testes para hypokrates.http.retry — todos os status retryable, backoff, Retry-After."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import httpx
import pytest
import respx

from hypokrates.constants import HTTPSettings
from hypokrates.exceptions import NetworkError, RateLimitError, SourceUnavailableError
from hypokrates.http.retry import _parse_retry_after, retry_request
from hypokrates.http.retry import calculate_backoff as _backoff
from hypokrates.http.settings import create_client


class TestRetrySuccess:
    """Requests bem-sucedidos."""

    @respx.mock
    async def test_successful_request(self) -> None:
        respx.get("https://example.com/api").mock(
            return_value=httpx.Response(200, json={"ok": True})
        )
        async with create_client() as client:
            response = await retry_request(client, "GET", "https://example.com/api")
            assert response.status_code == 200

    @respx.mock
    async def test_returns_response_body(self) -> None:
        respx.get("https://example.com/api").mock(
            return_value=httpx.Response(200, json={"data": "value"})
        )
        async with create_client() as client:
            response = await retry_request(client, "GET", "https://example.com/api")
            assert response.json() == {"data": "value"}


class TestRetryAllRetryableStatus:
    """Todos os status retryable definidos em _RETRYABLE_STATUS."""

    @pytest.mark.parametrize("status_code", [429, 500, 502, 503, 504])
    @respx.mock
    async def test_retryable_status_recovers(self, status_code: int) -> None:
        """Status retryable + recovery no segundo attempt."""
        route = respx.get("https://example.com/api")
        route.side_effect = [
            httpx.Response(status_code, headers={"Retry-After": "0"}),
            httpx.Response(200, json={"ok": True}),
        ]
        async with create_client() as client:
            with patch("hypokrates.http.retry.asyncio.sleep", new_callable=AsyncMock):
                response = await retry_request(
                    client,
                    "GET",
                    "https://example.com/api",
                    max_retries=2,
                    source_name="test",
                )
                assert response.status_code == 200

    @pytest.mark.parametrize("status_code", [500, 502, 503, 504])
    @respx.mock
    async def test_5xx_exhaustion_raises_source_unavailable(self, status_code: int) -> None:
        """Status 5xx persistente → SourceUnavailableError."""
        respx.get("https://example.com/api").mock(return_value=httpx.Response(status_code))
        async with create_client() as client:
            with (
                patch("hypokrates.http.retry.asyncio.sleep", new_callable=AsyncMock),
                pytest.raises((SourceUnavailableError, NetworkError)),
            ):
                await retry_request(
                    client,
                    "GET",
                    "https://example.com/api",
                    max_retries=0,
                    source_name="test",
                )

    @respx.mock
    async def test_429_exhaustion_raises_rate_limit(self) -> None:
        """429 persistente → RateLimitError."""
        respx.get("https://example.com/api").mock(
            return_value=httpx.Response(429, headers={"Retry-After": "1"})
        )
        async with create_client() as client:
            with pytest.raises(RateLimitError, match="test"):
                await retry_request(
                    client,
                    "GET",
                    "https://example.com/api",
                    max_retries=0,
                    source_name="test",
                )


class TestRetryBackoff:
    """Backoff exponencial segue a fórmula correta."""

    def test_backoff_sequence(self) -> None:
        """1s, 2s, 4s, 8s..."""
        assert _backoff(0) == pytest.approx(1.0)
        assert _backoff(1) == pytest.approx(2.0)
        assert _backoff(2) == pytest.approx(4.0)
        assert _backoff(3) == pytest.approx(8.0)

    def test_backoff_capped_at_max(self) -> None:
        """Nunca > BACKOFF_MAX (60s)."""
        assert _backoff(100) == HTTPSettings.BACKOFF_MAX

    def test_backoff_formula(self) -> None:
        """base * (factor ** attempt), capped."""
        for attempt in range(10):
            expected = min(
                HTTPSettings.BACKOFF_BASE * (HTTPSettings.BACKOFF_FACTOR**attempt),
                HTTPSettings.BACKOFF_MAX,
            )
            assert _backoff(attempt) == pytest.approx(expected)


class TestRetryAfterHeader:
    """Retry-After header respeitado pelo 429."""

    @respx.mock
    async def test_valid_retry_after(self) -> None:
        """'5' → wait 5s."""
        route = respx.get("https://example.com/api")
        route.side_effect = [
            httpx.Response(429, headers={"Retry-After": "5"}),
            httpx.Response(200, json={"ok": True}),
        ]
        sleep_patch = patch("hypokrates.http.retry.asyncio.sleep", new_callable=AsyncMock)
        async with create_client() as client:
            with sleep_patch as mock_sleep:
                await retry_request(
                    client,
                    "GET",
                    "https://example.com/api",
                    max_retries=2,
                    source_name="test",
                )
                mock_sleep.assert_called_once_with(5.0)

    @respx.mock
    async def test_invalid_retry_after_falls_to_backoff(self) -> None:
        """'abc' → backoff padrão."""
        route = respx.get("https://example.com/api")
        route.side_effect = [
            httpx.Response(429, headers={"Retry-After": "abc"}),
            httpx.Response(200, json={"ok": True}),
        ]
        sleep_patch = patch("hypokrates.http.retry.asyncio.sleep", new_callable=AsyncMock)
        async with create_client() as client:
            with sleep_patch as mock_sleep:
                await retry_request(
                    client,
                    "GET",
                    "https://example.com/api",
                    max_retries=2,
                    source_name="test",
                )
                mock_sleep.assert_called_once_with(_backoff(0))

    @respx.mock
    async def test_missing_retry_after_uses_backoff(self) -> None:
        """Sem header → backoff padrão."""
        route = respx.get("https://example.com/api")
        route.side_effect = [
            httpx.Response(429),
            httpx.Response(200, json={"ok": True}),
        ]
        sleep_patch = patch("hypokrates.http.retry.asyncio.sleep", new_callable=AsyncMock)
        async with create_client() as client:
            with sleep_patch as mock_sleep:
                await retry_request(
                    client,
                    "GET",
                    "https://example.com/api",
                    max_retries=2,
                    source_name="test",
                )
                mock_sleep.assert_called_once_with(_backoff(0))


class TestRetryAfterParsing:
    """Unit tests para _parse_retry_after."""

    def test_valid_integer(self) -> None:
        resp = httpx.Response(429, headers={"Retry-After": "5"})
        assert _parse_retry_after(resp) == 5.0

    def test_valid_float(self) -> None:
        resp = httpx.Response(429, headers={"Retry-After": "2.5"})
        assert _parse_retry_after(resp) == 2.5

    def test_invalid_value_returns_none(self) -> None:
        resp = httpx.Response(429, headers={"Retry-After": "abc"})
        assert _parse_retry_after(resp) is None

    def test_missing_header_returns_none(self) -> None:
        resp = httpx.Response(429)
        assert _parse_retry_after(resp) is None


class TestRetryExceptions:
    """Exceções corretas por tipo de falha."""

    @respx.mock
    async def test_timeout_retries_then_network_error(self) -> None:
        respx.get("https://example.com/api").mock(side_effect=httpx.ReadTimeout("timeout"))
        async with create_client() as client:
            with (
                patch("hypokrates.http.retry.asyncio.sleep", new_callable=AsyncMock),
                pytest.raises(NetworkError),
            ):
                await retry_request(
                    client,
                    "GET",
                    "https://example.com/api",
                    max_retries=1,
                    source_name="test",
                )

    @respx.mock
    async def test_connect_error_retries_then_network_error(self) -> None:
        respx.get("https://example.com/api").mock(
            side_effect=httpx.ConnectError("connection refused")
        )
        async with create_client() as client:
            with (
                patch("hypokrates.http.retry.asyncio.sleep", new_callable=AsyncMock),
                pytest.raises(NetworkError),
            ):
                await retry_request(
                    client,
                    "GET",
                    "https://example.com/api",
                    max_retries=1,
                    source_name="test",
                )

    @pytest.mark.parametrize("status_code", [400, 401, 403])
    @respx.mock
    async def test_4xx_raises_immediately_no_retry(self, status_code: int) -> None:
        """4xx não retryable → NetworkError imediato."""
        respx.get("https://example.com/api").mock(return_value=httpx.Response(status_code))
        async with create_client() as client:
            with pytest.raises(NetworkError):
                await retry_request(
                    client,
                    "GET",
                    "https://example.com/api",
                    max_retries=3,
                    source_name="test",
                )

    @respx.mock
    async def test_404_passthrough_returns_response(self) -> None:
        """404 é passthrough — retorna response pro caller tratar."""
        respx.get("https://example.com/api").mock(return_value=httpx.Response(404))
        async with create_client() as client:
            response = await retry_request(
                client,
                "GET",
                "https://example.com/api",
                max_retries=3,
                source_name="test",
            )
            assert response.status_code == 404

    @respx.mock
    async def test_500_final_attempt_source_unavailable(self) -> None:
        """500 na última tentativa → SourceUnavailableError."""
        respx.get("https://example.com/api").mock(return_value=httpx.Response(500))
        async with create_client() as client:
            with pytest.raises(SourceUnavailableError):
                await retry_request(
                    client,
                    "GET",
                    "https://example.com/api",
                    max_retries=0,
                    source_name="test",
                )

    @respx.mock
    async def test_retries_correct_number_of_times(self) -> None:
        """Verifica que tenta max_retries + 1 vezes."""
        route = respx.get("https://example.com/api")
        route.mock(return_value=httpx.Response(502))
        async with create_client() as client:
            with (
                patch("hypokrates.http.retry.asyncio.sleep", new_callable=AsyncMock),
                pytest.raises((SourceUnavailableError, NetworkError)),
            ):
                await retry_request(
                    client,
                    "GET",
                    "https://example.com/api",
                    max_retries=2,
                    source_name="test",
                )
            assert route.call_count == 3  # 1 original + 2 retries
