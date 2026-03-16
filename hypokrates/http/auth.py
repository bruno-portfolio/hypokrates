"""Autenticação e parsing compartilhados para clients NCBI (PubMed, MeSH)."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from hypokrates.config import get_config
from hypokrates.exceptions import ParseError, SourceUnavailableError

if TYPE_CHECKING:
    import httpx

    from hypokrates.http.base_client import ParamsType


def inject_ncbi_auth(params: ParamsType) -> None:
    """Injeta credenciais NCBI (email e api_key) nos parâmetros."""
    cfg = get_config()
    if cfg.ncbi_email:
        params["email"] = cfg.ncbi_email
    if cfg.ncbi_api_key:
        params["api_key"] = cfg.ncbi_api_key


def parse_ncbi_response(source: str, response: httpx.Response) -> dict[str, Any]:
    """Parseia JSON response NCBI com tratamento de erro padrão.

    Trata erros via campo "error" e "esearchresult.ERROR".
    Compartilhado entre PubMedClient e MeSHClient.
    """
    try:
        data: dict[str, Any] = response.json()
    except Exception as exc:
        raise ParseError(source, f"Invalid JSON: {exc}") from exc

    if "error" in data:
        raise SourceUnavailableError(source, str(data["error"]))

    esearch = data.get("esearchresult", {})
    if isinstance(esearch, dict) and "ERROR" in esearch:
        raise SourceUnavailableError(source, str(esearch["ERROR"]))

    return data
