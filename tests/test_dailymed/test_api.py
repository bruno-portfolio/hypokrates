"""Testes para hypokrates.dailymed.api."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import AsyncMock, patch

from hypokrates.dailymed.api import check_label, label_events
from tests.helpers import load_golden

GOLDEN_DATA = Path(__file__).parent.parent / "golden_data"


@patch("hypokrates.dailymed.api.DailyMedClient")
async def test_label_events_found(mock_client_cls: AsyncMock) -> None:
    """propofol → lista de adverse reactions."""
    golden_spls = load_golden("dailymed", "spls_propofol.json")
    golden_xml = (GOLDEN_DATA / "dailymed" / "spl_xml_propofol.xml").read_text()

    instance = AsyncMock()
    instance.search_spls.return_value = golden_spls
    instance.fetch_spl_xml.return_value = golden_xml
    mock_client_cls.return_value = instance

    result = await label_events("propofol")

    assert result.drug == "propofol"
    assert result.set_id == "b169a494-5042-4577-a5e2-f6b48b4c7e21"
    assert len(result.events) > 0
    assert result.meta.source == "DailyMed/FDA"
    instance.close.assert_called_once()


@patch("hypokrates.dailymed.api.DailyMedClient")
async def test_label_events_not_found(mock_client_cls: AsyncMock) -> None:
    """Droga não encontrada → resultado vazio."""
    instance = AsyncMock()
    instance.search_spls.return_value = {"data": []}
    mock_client_cls.return_value = instance

    result = await label_events("unknowndrug123")

    assert result.drug == "unknowndrug123"
    assert result.set_id is None
    assert result.events == []
    instance.fetch_spl_xml.assert_not_called()
    instance.close.assert_called_once()


@patch("hypokrates.dailymed.api.DailyMedClient")
async def test_check_label_in_label(mock_client_cls: AsyncMock) -> None:
    """propofol + bradycardia → in_label=True."""
    golden_spls = load_golden("dailymed", "spls_propofol.json")
    golden_xml = (GOLDEN_DATA / "dailymed" / "spl_xml_propofol.xml").read_text()

    instance = AsyncMock()
    instance.search_spls.return_value = golden_spls
    instance.fetch_spl_xml.return_value = golden_xml
    mock_client_cls.return_value = instance

    result = await check_label("propofol", "bradycardia")

    assert result.drug == "propofol"
    assert result.event == "bradycardia"
    assert result.in_label is True
    assert len(result.matched_terms) > 0
    assert result.meta.source == "DailyMed/FDA"


@patch("hypokrates.dailymed.api.DailyMedClient")
async def test_check_label_not_in_label(mock_client_cls: AsyncMock) -> None:
    """propofol + serotonin syndrome → in_label=False."""
    golden_spls = load_golden("dailymed", "spls_propofol.json")
    golden_xml = (GOLDEN_DATA / "dailymed" / "spl_xml_propofol.xml").read_text()

    instance = AsyncMock()
    instance.search_spls.return_value = golden_spls
    instance.fetch_spl_xml.return_value = golden_xml
    mock_client_cls.return_value = instance

    result = await check_label("propofol", "serotonin syndrome")

    assert result.in_label is False
    assert result.matched_terms == []


@patch("hypokrates.dailymed.api.DailyMedClient")
async def test_check_label_drug_not_found(mock_client_cls: AsyncMock) -> None:
    """Droga não encontrada → in_label=False."""
    instance = AsyncMock()
    instance.search_spls.return_value = {"data": []}
    mock_client_cls.return_value = instance

    result = await check_label("unknowndrug123", "bradycardia")

    assert result.in_label is False
    assert result.set_id is None
