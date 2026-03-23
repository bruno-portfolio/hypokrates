from __future__ import annotations

import os
from pathlib import Path

from hypokrates.config import configure
from hypokrates.mcp.server import create_server

# Env var → configure() mapping (lidos do .mcp.json ou shell)
_ENV_MAP: dict[str, str] = {
    "OPENFDA_API_KEY": "openfda_api_key",
    "NCBI_API_KEY": "ncbi_api_key",
    "NCBI_EMAIL": "ncbi_email",
    "DRUGBANK_PATH": "drugbank_path",
    "ONSIDES_PATH": "onsides_path",
    "CANADA_BULK_PATH": "canada_bulk_path",
    "JADER_BULK_PATH": "jader_bulk_path",
    "FAERS_BULK_DIR": "faers_bulk_dir",
}

_PATH_FIELDS = {
    "drugbank_path",
    "onsides_path",
    "canada_bulk_path",
    "jader_bulk_path",
    "faers_bulk_dir",
}


def _configure_from_env() -> None:
    """Lê env vars e aplica configure() automaticamente."""
    kwargs: dict[str, Path | str] = {}
    for env_var, config_field in _ENV_MAP.items():
        value = os.environ.get(env_var)
        if value:
            kwargs[config_field] = Path(value) if config_field in _PATH_FIELDS else value
    if kwargs:
        configure(**kwargs)


_configure_from_env()
mcp = create_server()
mcp.run()
