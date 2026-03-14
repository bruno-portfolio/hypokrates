"""Testes para hypokrates.config — singleton, validação, thread safety."""

from __future__ import annotations

import threading
from typing import TYPE_CHECKING

import pytest

from hypokrates.config import configure, get_config, reset_config

if TYPE_CHECKING:
    from pathlib import Path


class TestGetConfig:
    """Valores padrão e singleton."""

    def test_returns_default_config(self) -> None:
        cfg = get_config()
        assert cfg.cache_enabled is True
        assert cfg.http_timeout == 30.0
        assert cfg.http_max_retries == 3
        assert cfg.openfda_api_key is None
        assert cfg.debug is False

    def test_singleton_returns_same_instance(self) -> None:
        cfg1 = get_config()
        cfg2 = get_config()
        assert cfg1 is cfg2

    def test_default_cache_dir_is_set(self) -> None:
        cfg = get_config()
        assert cfg.cache_dir is not None
        assert "hypokrates" in str(cfg.cache_dir)


class TestConfigure:
    """Atualização e validação de configuração."""

    def test_updates_config_values(self) -> None:
        configure(debug=True, http_timeout=60.0)
        cfg = get_config()
        assert cfg.debug is True
        assert cfg.http_timeout == 60.0

    def test_rejects_unknown_keys(self) -> None:
        with pytest.raises(TypeError, match="Configuração desconhecida"):
            configure(unknown_key="value")

    def test_updates_cache_dir(self, tmp_path: Path) -> None:
        configure(cache_dir=tmp_path)
        cfg = get_config()
        assert cfg.cache_dir == tmp_path

    def test_updates_api_key(self) -> None:
        configure(openfda_api_key="test-key")
        cfg = get_config()
        assert cfg.openfda_api_key == "test-key"

    def test_updates_cache_enabled(self) -> None:
        configure(cache_enabled=False)
        cfg = get_config()
        assert cfg.cache_enabled is False

    def test_updates_max_retries(self) -> None:
        configure(http_max_retries=5)
        cfg = get_config()
        assert cfg.http_max_retries == 5

    def test_multiple_updates_accumulate(self) -> None:
        configure(debug=True)
        configure(http_timeout=60.0)
        cfg = get_config()
        assert cfg.debug is True
        assert cfg.http_timeout == 60.0


class TestResetConfig:
    """Reset cria nova instância limpa."""

    def test_reset_creates_fresh_instance(self) -> None:
        configure(debug=True)
        reset_config()
        cfg = get_config()
        assert cfg.debug is False

    def test_reset_clears_api_key(self) -> None:
        configure(openfda_api_key="test-key")
        reset_config()
        cfg = get_config()
        assert cfg.openfda_api_key is None

    def test_reset_returns_to_defaults(self) -> None:
        configure(
            debug=True,
            http_timeout=99.0,
            http_max_retries=10,
            cache_enabled=False,
        )
        reset_config()
        cfg = get_config()
        assert cfg.debug is False
        assert cfg.http_timeout == 30.0
        assert cfg.http_max_retries == 3
        assert cfg.cache_enabled is True


class TestConfigThreadSafety:
    """Config singleton é thread-safe."""

    def test_concurrent_get_config_returns_same(self) -> None:
        """Múltiplas threads pegam o mesmo singleton."""
        results: list[object] = []
        errors: list[Exception] = []

        def get_and_store() -> None:
            try:
                cfg = get_config()
                results.append(id(cfg))
            except Exception as exc:
                errors.append(exc)

        threads = [threading.Thread(target=get_and_store) for _ in range(10)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert not errors
        assert len(set(results)) == 1  # Todos pegaram o mesmo objeto
