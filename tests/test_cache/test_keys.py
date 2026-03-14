"""Testes para hypokrates.cache.keys — determinismo, colisões, caracteres especiais."""

from __future__ import annotations

from hypokrates.cache.keys import cache_key


class TestCacheKeyFormat:
    """Formato correto da cache key."""

    def test_basic_key_format(self) -> None:
        key = cache_key("faers", "/drug/event.json")
        assert key.startswith("faers:/drug/event.json|")
        assert key.endswith("|v1")

    def test_no_params_uses_none(self) -> None:
        key = cache_key("faers", "/drug/event.json")
        assert "|none|" in key

    def test_with_params_uses_hash(self) -> None:
        key = cache_key("faers", "/drug/event.json", {"drug": "propofol"})
        assert "|none|" not in key
        # Hash é 16 chars hex
        parts = key.split("|")
        assert len(parts) == 3
        assert len(parts[1]) == 16


class TestCacheKeyDeterminism:
    """Mesmos inputs → mesma key, sempre."""

    def test_same_params_same_key(self) -> None:
        params = {"drug": "propofol", "limit": 100}
        key1 = cache_key("faers", "/drug/event.json", params)
        key2 = cache_key("faers", "/drug/event.json", params)
        assert key1 == key2

    def test_param_order_irrelevant(self) -> None:
        key1 = cache_key("faers", "/drug/event.json", {"a": 1, "b": 2})
        key2 = cache_key("faers", "/drug/event.json", {"b": 2, "a": 1})
        assert key1 == key2

    def test_deterministic_across_100_runs(self) -> None:
        params = {"drug": "propofol", "limit": 100, "skip": 0}
        baseline = cache_key("faers", "/drug/event.json", params)
        for _ in range(99):
            assert cache_key("faers", "/drug/event.json", params) == baseline


class TestCacheKeyCollision:
    """Keys diferentes para inputs diferentes."""

    def test_different_params_different_key(self) -> None:
        key1 = cache_key("faers", "/drug/event.json", {"drug": "propofol"})
        key2 = cache_key("faers", "/drug/event.json", {"drug": "ketamine"})
        assert key1 != key2

    def test_different_sources_different_key(self) -> None:
        key1 = cache_key("faers", "/drug/event.json", {"drug": "propofol"})
        key2 = cache_key("pubmed", "/drug/event.json", {"drug": "propofol"})
        assert key1 != key2

    def test_different_endpoints_different_key(self) -> None:
        key1 = cache_key("faers", "/drug/event.json", {"drug": "propofol"})
        key2 = cache_key("faers", "/drug/label.json", {"drug": "propofol"})
        assert key1 != key2


class TestCacheKeySpecialChars:
    """Caracteres especiais nos parâmetros."""

    def test_params_with_quotes(self) -> None:
        key = cache_key("faers", "/api", {"search": 'drug:"PROPOFOL"'})
        assert isinstance(key, str)

    def test_params_with_unicode(self) -> None:
        key = cache_key("faers", "/api", {"search": "propoföl"})
        assert isinstance(key, str)

    def test_params_with_none_value(self) -> None:
        key = cache_key("faers", "/api", {"key": None})
        assert isinstance(key, str)

    def test_params_with_boolean(self) -> None:
        key1 = cache_key("faers", "/api", {"flag": True})
        key2 = cache_key("faers", "/api", {"flag": False})
        assert key1 != key2
