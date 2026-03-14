"""Testes para hypokrates.cache.policies — TTL por fonte."""

from __future__ import annotations

from hypokrates.cache.policies import get_ttl
from hypokrates.constants import CacheSettings, Source


class TestGetTTL:
    """TTL correto por fonte."""

    def test_faers_ttl(self) -> None:
        assert get_ttl(Source.FAERS) == CacheSettings.FAERS_TTL

    def test_faers_ttl_is_24h(self) -> None:
        assert get_ttl(Source.FAERS) == 86_400

    def test_unknown_source_uses_default(self) -> None:
        assert get_ttl("unknown_source") == CacheSettings.DEFAULT_TTL

    def test_default_ttl_is_24h(self) -> None:
        assert CacheSettings.DEFAULT_TTL == 86_400

    def test_vocab_ttl_is_90_days(self) -> None:
        assert CacheSettings.VOCAB_TTL == 7_776_000
