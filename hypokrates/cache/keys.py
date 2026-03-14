"""Geração de cache keys determinísticas."""

from __future__ import annotations

import hashlib
import json

from hypokrates.constants import CacheSettings


def cache_key(
    source: str,
    endpoint: str,
    params: dict[str, str | int | float | bool | None] | None = None,
) -> str:
    """Gera cache key no formato ``{source}:{endpoint}|{params_hash}|v{ver}``.

    Parâmetros são ordenados e hasheados para garantir determinismo.
    """
    params_hash = _hash_params(params) if params else "none"
    return f"{source}:{endpoint}|{params_hash}|v{CacheSettings.SCHEMA_VERSION}"


def _hash_params(params: dict[str, str | int | float | bool | None]) -> str:
    """Hash SHA-256 truncado dos parâmetros ordenados."""
    sorted_json = json.dumps(params, sort_keys=True, default=str)
    return hashlib.sha256(sorted_json.encode()).hexdigest()[:16]
