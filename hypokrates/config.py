"""Configuração global do hypokrates — singleton thread-safe."""

from __future__ import annotations

import threading
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class HypokratesConfig:
    """Configuração global do hypokrates.

    Singleton acessível via ``get_config()`` e configurável via ``configure()``.
    """

    # Cache
    cache_dir: Path = field(default_factory=lambda: Path.home() / ".cache" / "hypokrates")
    cache_enabled: bool = True

    # HTTP
    http_timeout: float = 30.0
    http_max_retries: int = 3

    # OpenFDA
    openfda_api_key: str | None = None

    # NCBI / PubMed
    ncbi_api_key: str | None = None
    ncbi_email: str | None = None

    # DrugBank
    drugbank_path: Path | None = None

    # Verbosity
    debug: bool = False


_lock = threading.RLock()
_config: HypokratesConfig | None = None


def get_config() -> HypokratesConfig:
    """Retorna a configuração global (cria default na primeira chamada)."""
    global _config
    if _config is None:
        with _lock:
            if _config is None:
                _config = HypokratesConfig()
    return _config


def configure(**kwargs: object) -> HypokratesConfig:
    """Atualiza a configuração global.

    Aceita os mesmos campos de ``HypokratesConfig``.
    """
    global _config
    with _lock:
        cfg = get_config()
        for key, value in kwargs.items():
            if not hasattr(cfg, key):
                msg = f"Configuração desconhecida: {key}"
                raise TypeError(msg)
            setattr(cfg, key, value)
        return cfg


def reset_config() -> None:
    """Reseta para config default (usado em testes)."""
    global _config
    with _lock:
        _config = None
