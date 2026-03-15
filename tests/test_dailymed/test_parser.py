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
        # Verifica termos de Adverse Reactions (case-insensitive check)
        lower_terms = [t.lower() for t in terms]
        assert any("bradycardia" in t for t in lower_terms)
        assert any("hypotension" in t for t in lower_terms)
        # Verifica termos de Boxed Warning
        assert any("qt prolongation" in t for t in lower_terms)
        assert any("cardiac arrest" in t for t in lower_terms)
        # Verifica termos de Warnings and Precautions
        assert any("hyperlipidemia" in t for t in lower_terms)
        assert any("myoclonia" in t for t in lower_terms)

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

    def test_multiple_safety_sections(self) -> None:
        """Verifica que todas as seções de segurança são parseadas."""
        xml = """<?xml version="1.0" encoding="UTF-8"?>
        <document xmlns="urn:hl7-org:v3">
          <component>
            <structuredBody>
              <component>
                <section>
                  <code code="34066-1" codeSystem="2.16.840.1.113883.6.1"/>
                  <text><paragraph>Black box: Hepatotoxicity reported.</paragraph></text>
                </section>
              </component>
              <component>
                <section>
                  <code code="34071-1" codeSystem="2.16.840.1.113883.6.1"/>
                  <text><paragraph>Renal impairment may occur.</paragraph></text>
                </section>
              </component>
              <component>
                <section>
                  <code code="43685-7" codeSystem="2.16.840.1.113883.6.1"/>
                  <text><paragraph>Thrombocytopenia has been observed.</paragraph></text>
                </section>
              </component>
              <component>
                <section>
                  <code code="34084-4" codeSystem="2.16.840.1.113883.6.1"/>
                  <text><paragraph>Nausea, Vomiting, Diarrhea</paragraph></text>
                </section>
              </component>
            </structuredBody>
          </component>
        </document>"""
        terms, raw_text = parse_adverse_reactions_xml(xml)

        lower_terms = [t.lower() for t in terms]
        # Adverse Reactions
        assert any("nausea" in t for t in lower_terms)
        assert any("diarrhea" in t for t in lower_terms)
        # Boxed Warning
        assert any("hepatotoxicity" in t for t in lower_terms)
        # Warnings (old format)
        assert any("renal impairment" in t for t in lower_terms)
        # Warnings and Precautions (PLR format)
        assert any("thrombocytopenia" in t for t in lower_terms)
        # raw_text contém texto de todas as seções
        assert "Hepatotoxicity" in raw_text
        assert "Renal impairment" in raw_text
        assert "Thrombocytopenia" in raw_text
        assert "Nausea" in raw_text

    def test_boxed_warning_only(self) -> None:
        """Verifica que XML com apenas Boxed Warning (sem Adverse Reactions) funciona."""
        xml = """<?xml version="1.0" encoding="UTF-8"?>
        <document xmlns="urn:hl7-org:v3">
          <component>
            <structuredBody>
              <component>
                <section>
                  <code code="34066-1" codeSystem="2.16.840.1.113883.6.1"/>
                  <text>
                    <paragraph>WARNING: Risk of serious infections and malignancies.</paragraph>
                    <paragraph>Tuberculosis reactivation has been reported.</paragraph>
                  </text>
                </section>
              </component>
              <component>
                <section>
                  <code code="34068-7" codeSystem="2.16.840.1.113883.6.1"/>
                  <text><paragraph>Dose info only.</paragraph></text>
                </section>
              </component>
            </structuredBody>
          </component>
        </document>"""
        terms, raw_text = parse_adverse_reactions_xml(xml)

        assert len(terms) > 0
        assert raw_text != ""
        lower_terms = [t.lower() for t in terms]
        assert any("tuberculosis" in t for t in lower_terms)
        assert any("malignancies" in t for t in lower_terms)

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
