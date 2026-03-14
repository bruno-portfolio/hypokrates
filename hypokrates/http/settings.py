"""Configuração do httpx client."""

from __future__ import annotations

import httpx

from hypokrates.constants import USER_AGENT, HTTPSettings


def create_client(
    *,
    timeout: float | None = None,
    base_url: str = "",
) -> httpx.AsyncClient:
    """Cria um httpx.AsyncClient com headers e timeout padrão."""
    return httpx.AsyncClient(
        base_url=base_url,
        timeout=httpx.Timeout(timeout or HTTPSettings.TIMEOUT),
        headers={
            "User-Agent": USER_AGENT,
            "Accept": "application/json",
        },
        follow_redirects=True,
    )
