"""Autenticação compartilhada para clients NCBI (PubMed, MeSH)."""

from __future__ import annotations

from typing import TYPE_CHECKING

from hypokrates.config import get_config

if TYPE_CHECKING:
    from hypokrates.http.base_client import ParamsType


def inject_ncbi_auth(params: ParamsType) -> None:
    """Injeta credenciais NCBI (email e api_key) nos parâmetros."""
    cfg = get_config()
    if cfg.ncbi_email:
        params["email"] = cfg.ncbi_email
    if cfg.ncbi_api_key:
        params["api_key"] = cfg.ncbi_api_key
