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


@patch("hypokrates.dailymed.api.DailyMedClient")
async def test_label_events_skips_spl_without_safety(mock_client_cls: AsyncMock) -> None:
    """Bug 3: SPL sem safety sections (powder) deve ser ignorado."""
    golden_spls = load_golden("dailymed", "spls_gabapentin_multi.json")
    golden_xml_real = (GOLDEN_DATA / "dailymed" / "spl_xml_propofol.xml").read_text()

    # XML sem safety sections (powder SPL)
    powder_xml = """<?xml version="1.0" encoding="UTF-8"?>
    <document xmlns="urn:hl7-org:v3">
      <component><structuredBody><component><section>
        <code code="34068-7" codeSystem="2.16.840.1.113883.6.1"/>
        <text><paragraph>Dosage info only.</paragraph></text>
      </section></component></structuredBody></component>
    </document>"""

    instance = AsyncMock()
    instance.search_spls.return_value = golden_spls
    # First SPL (powder) has no safety sections, second has
    instance.fetch_spl_xml.side_effect = [powder_xml, golden_xml_real]
    mock_client_cls.return_value = instance

    result = await label_events("gabapentin")

    assert result.drug == "gabapentin"
    # Should use second SPL (with safety sections), not the powder
    assert result.set_id == "bbbb-capsule-with-safety"
    assert len(result.events) > 0
    instance.close.assert_called_once()


@patch("hypokrates.dailymed.api.DailyMedClient")
async def test_label_events_fallback_when_no_safety(mock_client_cls: AsyncMock) -> None:
    """Quando nenhum SPL tem safety sections, usa o primeiro (fallback)."""
    golden_spls = {
        "data": [
            {"setid": "aaa-no-safety", "title": "Test Drug Powder"},
            {"setid": "bbb-no-safety", "title": "Test Drug OTC"},
        ],
        "metadata": {"total_elements": 2},
    }

    no_safety_xml = """<?xml version="1.0" encoding="UTF-8"?>
    <document xmlns="urn:hl7-org:v3">
      <component><structuredBody><component><section>
        <code code="34068-7" codeSystem="2.16.840.1.113883.6.1"/>
        <text><paragraph>Dosage info only.</paragraph></text>
      </section></component></structuredBody></component>
    </document>"""

    instance = AsyncMock()
    instance.search_spls.return_value = golden_spls
    # All SPLs lack safety sections; fallback re-fetches first
    instance.fetch_spl_xml.return_value = no_safety_xml
    mock_client_cls.return_value = instance

    result = await label_events("testdrug")

    assert result.drug == "testdrug"
    assert result.set_id == "aaa-no-safety"
    assert result.events == []
    instance.close.assert_called_once()
