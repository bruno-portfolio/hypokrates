"""Testes para hypokrates.http.settings — factory de client HTTP."""

from __future__ import annotations

from hypokrates.constants import USER_AGENT, HTTPSettings
from hypokrates.http.settings import create_client


class TestCreateClient:
    """Factory cria client com configuração correta."""

    async def test_creates_client_with_user_agent(self) -> None:
        client = create_client()
        assert client.headers["User-Agent"] == USER_AGENT
        await client.aclose()

    async def test_creates_client_with_default_timeout(self) -> None:
        client = create_client()
        assert client.timeout.connect == HTTPSettings.TIMEOUT
        await client.aclose()

    async def test_creates_client_with_custom_timeout(self) -> None:
        client = create_client(timeout=60.0)
        assert client.timeout.connect == 60.0
        await client.aclose()

    async def test_creates_client_with_base_url(self) -> None:
        client = create_client(base_url="https://api.example.com")
        assert str(client.base_url) == "https://api.example.com"
        await client.aclose()

    async def test_creates_client_with_accept_json(self) -> None:
        client = create_client()
        assert client.headers["Accept"] == "application/json"
        await client.aclose()

    async def test_creates_client_follows_redirects(self) -> None:
        client = create_client()
        assert client.follow_redirects is True
        await client.aclose()
