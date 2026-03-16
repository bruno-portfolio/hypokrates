"""Fixtures compartilhadas para testes de scan."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest


@pytest.fixture(autouse=True)
def _disable_bulk_autodetect() -> object:  # type: ignore[misc]
    """Desabilita auto-detect de FAERS Bulk em testes que não testam bulk.

    Sem isto, testes que mockam faers_api.top_events falham em máquinas
    com faers_bulk.duckdb carregado (12GB), pois _check_bulk_available()
    retorna True e o scan ignora o mock.

    Testes que explicitamente passam use_bulk=True ou mockam
    _check_bulk_available já controlam o comportamento.
    """
    with patch(
        "hypokrates.scan.api._check_bulk_available",
        new_callable=AsyncMock,
        return_value=False,
    ):
        yield
