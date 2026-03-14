"""TTL policies por fonte de dados."""

from __future__ import annotations

from hypokrates.constants import CacheSettings, Source

_TTL_MAP: dict[str, int] = {
    Source.FAERS: CacheSettings.FAERS_TTL,
    Source.PUBMED: CacheSettings.DEFAULT_TTL,
}


def get_ttl(source: str) -> int:
    """Retorna TTL em segundos para uma fonte."""
    return _TTL_MAP.get(source, CacheSettings.DEFAULT_TTL)
