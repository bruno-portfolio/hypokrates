"""Testes para hypokrates.dailymed.parser."""

from __future__ import annotations

from pathlib import Path

from hypokrates.dailymed.parser import (
    match_event_in_label,
    parse_adverse_reactions_xml,
    parse_spl_search,
)
from tests.helpers import load_golden

GOLDEN_DATA = Path(__file__).parent.parent / "golden_data"


class TestParseSplSearch:
    """parse_spl_search — extrai SET IDs."""

    def test_propofol(self) -> None:
        data = load_golden("dailymed", "spls_propofol.json")
        set_ids = parse_spl_search(data)
        assert len(set_ids) == 1
        assert set_ids[0] == "b169a494-5042-4577-a5e2-f6b48b4c7e21"

    def test_empty_results(self) -> None:
        set_ids = parse_spl_search({"data": []})
        assert set_ids == []

    def test_missing_data_key(self) -> None:
        set_ids = parse_spl_search({})
        assert set_ids == []

    def test_missing_setid(self) -> None:
        set_ids = parse_spl_search({"data": [{"title": "test"}]})
        assert set_ids == []


class TestParseAdverseReactionsXml:
    """parse_adverse_reactions_xml — extrai termos do XML."""

    def test_propofol_xml(self) -> None:
        xml_path = GOLDEN_DATA / "dailymed" / "spl_xml_propofol.xml"
        xml_text = xml_path.read_text()
        terms, raw_text = parse_adverse_reactions_xml(xml_text)

        assert len(terms) > 0
        assert raw_text != ""
        # Verifica termos específicos (case-insensitive check)
        lower_terms = [t.lower() for t in terms]
        assert any("bradycardia" in t for t in lower_terms)
        assert any("hypotension" in t for t in lower_terms)

    def test_invalid_xml(self) -> None:
        terms, raw_text = parse_adverse_reactions_xml("not xml at all")
        assert terms == []
        assert raw_text == ""

    def test_xml_without_adverse_reactions(self) -> None:
        xml = """<?xml version="1.0" encoding="UTF-8"?>
        <document xmlns="urn:hl7-org:v3">
          <component>
            <structuredBody>
              <component>
                <section>
                  <code code="34068-7" codeSystem="2.16.840.1.113883.6.1"/>
                  <text><paragraph>Dose info.</paragraph></text>
                </section>
              </component>
            </structuredBody>
          </component>
        </document>"""
        terms, raw_text = parse_adverse_reactions_xml(xml)
        assert terms == []
        assert raw_text == ""

    def test_empty_adverse_reactions(self) -> None:
        xml = """<?xml version="1.0" encoding="UTF-8"?>
        <document xmlns="urn:hl7-org:v3">
          <component>
            <structuredBody>
              <component>
                <section>
                  <code code="34084-4" codeSystem="2.16.840.1.113883.6.1"/>
                  <text></text>
                </section>
              </component>
            </structuredBody>
          </component>
        </document>"""
        terms, _raw_text = parse_adverse_reactions_xml(xml)
        assert terms == []


class TestMatchEventInLabel:
    """match_event_in_label — case-insensitive substring matching."""

    def test_exact_match(self) -> None:
        found, matched = match_event_in_label("Bradycardia", ["Bradycardia", "Hypotension"])
        assert found is True
        assert "Bradycardia" in matched

    def test_case_insensitive(self) -> None:
        found, _matched = match_event_in_label("BRADYCARDIA", ["bradycardia"])
        assert found is True

    def test_substring_match(self) -> None:
        found, _matched = match_event_in_label("bradycardia", ["Cardiac disorders: Bradycardia"])
        assert found is True

    def test_reverse_substring(self) -> None:
        found, _matched = match_event_in_label("Cardiac disorders: Bradycardia", ["Bradycardia"])
        assert found is True

    def test_no_match(self) -> None:
        found, matched = match_event_in_label("serotonin syndrome", ["Bradycardia", "Hypotension"])
        assert found is False
        assert matched == []

    def test_fallback_raw_text(self) -> None:
        found, _matched = match_event_in_label(
            "pancreatitis", [], raw_text="Rare cases of pancreatitis have been reported."
        )
        assert found is True

    def test_no_fallback_when_terms_match(self) -> None:
        found, matched = match_event_in_label(
            "nausea",
            ["Nausea"],
            raw_text="Nausea was common.",
        )
        assert found is True
        assert len(matched) == 1
