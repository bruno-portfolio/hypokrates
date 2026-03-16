"""Fixtures compartilhadas para testes de stats."""

from __future__ import annotations

from collections.abc import Generator
from unittest.mock import AsyncMock, patch

import pytest


@pytest.fixture(autouse=True)
def _disable_bulk_autodetect() -> Generator[None, None, None]:
    """Desabilita auto-detect de FAERS Bulk em testes de stats.

    Mocka is_bulk_available()=False para que testes com use_bulk=None
    não usem bulk real. Testes de auto-detect re-patcheiam com
    @patch(..., return_value=True).
    """
    with patch(
        "hypokrates.faers_bulk.api.is_bulk_available",
        new_callable=AsyncMock,
        return_value=False,
    ):
        yield
