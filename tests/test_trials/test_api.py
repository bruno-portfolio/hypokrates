"""Testes para hypokrates.trials.api."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

from hypokrates.trials.api import search_trials
from tests.helpers import load_golden


def _mock_client(mock_cls: AsyncMock, instance: AsyncMock) -> None:
    """Configura mock para suportar async with (context manager)."""
    instance.__aenter__ = AsyncMock(return_value=instance)
    mock_cls.return_value = instance


@patch("hypokrates.trials.api.TrialsClient")
async def test_search_trials_found(mock_client_cls: AsyncMock) -> None:
    """propofol + hypotension → 3 trials, 2 active."""
    golden = load_golden("trials", "studies_propofol_hypotension.json")
    instance = AsyncMock()
    instance.search.return_value = golden
    _mock_client(mock_client_cls, instance)

    result = await search_trials("propofol", "hypotension")

    assert result.drug == "propofol"
    assert result.event == "hypotension"
    assert result.total_count == 3
    assert result.active_count == 2
    assert len(result.trials) == 3
    assert result.meta.source == "ClinicalTrials.gov"


@patch("hypokrates.trials.api.TrialsClient")
async def test_search_trials_empty(mock_client_cls: AsyncMock) -> None:
    """Sem trials → resultado vazio."""
    instance = AsyncMock()
    instance.search.return_value = {"totalCount": 0, "studies": []}
    _mock_client(mock_client_cls, instance)

    result = await search_trials("unknowndrug", "unknownevent")

    assert result.total_count == 0
    assert result.active_count == 0
    assert result.trials == []


@patch("hypokrates.trials.api.TrialsClient")
async def test_search_trials_active_count(mock_client_cls: AsyncMock) -> None:
    """Verifica contagem de trials ativos."""
    golden = load_golden("trials", "studies_propofol_hypotension.json")
    instance = AsyncMock()
    instance.search.return_value = golden
    _mock_client(mock_client_cls, instance)

    result = await search_trials("propofol", "hypotension")

    # RECRUITING + ACTIVE_NOT_RECRUITING = 2
    assert result.active_count == 2
    # Verify specific trial info
    nct_ids = [t.nct_id for t in result.trials]
    assert "NCT05001234" in nct_ids
