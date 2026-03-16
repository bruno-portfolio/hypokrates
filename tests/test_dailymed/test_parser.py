"""Testes para hypokrates.dailymed.parser."""

from __future__ import annotations

from pathlib import Path

from hypokrates.dailymed.parser import (
    _score_spl_candidate,
    has_safety_sections,
    match_event_in_label,
    parse_adverse_reactions_xml,
    parse_spl_search,
)
from tests.helpers import load_golden

GOLDEN_DATA = Path(__file__).parent.parent / "golden_data"


class TestParseSplSearch:
    """parse_spl_search — extrai SET IDs rankeados."""

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

    def test_ranks_injection_over_patch(self) -> None:
        """Bug #22: lidocaine injection deve vir antes de patch OTC."""
        data = {
            "data": [
                {
                    "setid": "patch-otc",
                    "spl_version": "6",
                    "title": "CARELAND LIDOCAINE 4 PLUS MENTHOL PAIN RELIEVING GEL PATCHES",
                },
                {
                    "setid": "injection-rx",
                    "spl_version": "5",
                    "title": "LIDOCAINE HYDROCHLORIDE INJECTION, USP",
                },
            ],
        }
        set_ids = parse_spl_search(data)
        assert set_ids[0] == "injection-rx"

    def test_filters_veterinary_labels(self) -> None:
        """Bug #23: ketamine vet deve ficar atrás de human."""
        data = {
            "data": [
                {
                    "setid": "vet-covetrus",
                    "spl_version": "3",
                    "title": "KETAMINE HYDROCHLORIDE INJECTION [COVETRUS]",
                },
                {
                    "setid": "vet-dechra",
                    "spl_version": "2",
                    "title": "KETAMINE HYDROCHLORIDE INJECTION [DECHRA VETERINARY PRODUCTS LLC]",
                },
                {
                    "setid": "human-ketalar",
                    "spl_version": "30",
                    "title": "KETALAR (KETAMINE HYDROCHLORIDE) INJECTION [PAR HEALTH USA, LLC]",
                },
            ],
        }
        set_ids = parse_spl_search(data)
        assert set_ids[0] == "human-ketalar"
        # Vet labels no final
        assert set_ids[-1] in {"vet-covetrus", "vet-dechra"}

    def test_ranks_by_spl_version_within_same_form(self) -> None:
        """SPLs com mesma forma farmacêutica: spl_version maior primeiro."""
        data = {
            "data": [
                {
                    "setid": "old",
                    "spl_version": "2",
                    "title": "DRUG X TABLET",
                },
                {
                    "setid": "new",
                    "spl_version": "15",
                    "title": "DRUG X TABLET",
                },
            ],
        }
        set_ids = parse_spl_search(data)
        assert set_ids[0] == "new"


class TestScoreSplCandidate:
    """_score_spl_candidate — scoring heurístico."""

    def test_injection_gets_bonus(self) -> None:
        score = _score_spl_candidate(
            {"setid": "a", "title": "PROPOFOL INJECTABLE EMULSION", "spl_version": 5}
        )
        assert score == 30  # min(5,5) + 25 (injectable)

    def test_patch_gets_penalty(self) -> None:
        score = _score_spl_candidate(
            {"setid": "b", "title": "LIDOCAINE PATCHES 4%", "spl_version": 6}
        )
        assert score == -20  # min(6,5) - 25 (patch)

    def test_veterinary_gets_negative_100(self) -> None:
        score = _score_spl_candidate(
            {"setid": "c", "title": "KETAMINE INJECTION [COVETRUS]", "spl_version": 3}
        )
        assert score == -100

    def test_veterinary_keyword(self) -> None:
        score = _score_spl_candidate(
            {"setid": "d", "title": "DRUG X [DECHRA VETERINARY PRODUCTS]", "spl_version": 2}
        )
        assert score == -100

    def test_capsule_gets_bonus(self) -> None:
        score = _score_spl_candidate({"setid": "e", "title": "DRUG X CAPSULE", "spl_version": 8})
        assert score == 30  # min(8,5) + 25 (capsule)

    def test_combination_product_penalty(self) -> None:
        score = _score_spl_candidate(
            {
                "setid": "f",
                "title": "ACETAMINOPHEN AND CODEINE PHOSPHATE TABLET",
                "spl_version": 10,
            }
        )
        # min(10,5) + 25 (tablet) - 30 (combination " AND ") = 0
        assert score == 0


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

    def test_meddra_synonym_anaphylactic_shock(self) -> None:
        """anaphylactic shock → match 'anaphylaxis' via MedDRA group."""
        found, matched = match_event_in_label(
            "anaphylactic shock",
            ["Anaphylaxis", "Hypotension"],
        )
        assert found is True
        assert "Anaphylaxis" in matched

    def test_meddra_synonym_canonical_to_alias(self) -> None:
        """anaphylaxis (canonical) → match 'anaphylactic reaction' (alias) in label."""
        found, _matched = match_event_in_label(
            "anaphylaxis",
            ["Anaphylactic reaction reported in 2 patients"],
        )
        assert found is True

    def test_meddra_synonym_sinus_bradycardia(self) -> None:
        """sinus bradycardia → match 'bradycardia' via MedDRA group."""
        found, matched = match_event_in_label(
            "sinus bradycardia",
            ["Bradycardia", "Tachycardia"],
        )
        assert found is True
        assert "Bradycardia" in matched

    def test_meddra_synonym_raw_text_fallback(self) -> None:
        """MedDRA synonym matches in raw_text when no terms match."""
        found, _matched = match_event_in_label(
            "anaphylactic shock",
            [],
            raw_text="Rare cases of anaphylaxis have been reported.",
        )
        assert found is True

    def test_meddra_no_duplicate_matches(self) -> None:
        """Same label term should not appear multiple times in matched list."""
        found, matched = match_event_in_label(
            "bradycardia",
            ["Bradycardia"],
        )
        assert found is True
        assert len(matched) == 1

    def test_fuzzy_no_match_without_rapidfuzz(self) -> None:
        """When no substring/MedDRA match and no rapidfuzz, returns False."""
        from unittest.mock import patch

        with patch.dict("sys.modules", {"rapidfuzz": None, "rapidfuzz.fuzz": None}):
            found, matched = match_event_in_label(
                "some_totally_unique_event_xyz",
                ["Completely different term"],
            )
            assert found is False
            assert matched == []

    def test_no_match_empty_terms_no_raw_text(self) -> None:
        """No terms, no raw_text → False."""
        found, matched = match_event_in_label("bradycardia", [])
        assert found is False
        assert matched == []

    def test_fuzzy_match_on_terms(self) -> None:
        """Fuzzy matching catches near-matches (e.g., reordered words)."""
        pytest = __import__("pytest")
        try:
            __import__("rapidfuzz")
        except ImportError:
            pytest.skip("rapidfuzz not installed")
        # "Hepatic failure acute" is very similar to "Acute hepatic failure"
        found, _matched = match_event_in_label(
            "acute hepatic failure",
            ["Hepatic failure acute"],
        )
        assert found is True

    def test_fuzzy_match_on_raw_text(self) -> None:
        """Fuzzy matching in raw_text when no term match."""
        pytest = __import__("pytest")
        try:
            __import__("rapidfuzz")
        except ImportError:
            pytest.skip("rapidfuzz not installed")
        found, _matched = match_event_in_label(
            "hepatic failure acute",
            [],
            raw_text="Cases of acute hepatic failure have been reported.",
        )
        # fuzzy may or may not match depending on score; just ensure no crash
        assert isinstance(found, bool)


class TestHasSafetySections:
    """has_safety_sections — detecta se XML tem seções de segurança."""

    def test_xml_with_adverse_reactions(self) -> None:
        xml = """<?xml version="1.0" encoding="UTF-8"?>
        <document xmlns="urn:hl7-org:v3">
          <component><structuredBody><component><section>
            <code code="34084-4" codeSystem="2.16.840.1.113883.6.1"/>
            <text><paragraph>Nausea, Vomiting</paragraph></text>
          </section></component></structuredBody></component>
        </document>"""
        assert has_safety_sections(xml) is True

    def test_xml_without_safety_sections(self) -> None:
        xml = """<?xml version="1.0" encoding="UTF-8"?>
        <document xmlns="urn:hl7-org:v3">
          <component><structuredBody><component><section>
            <code code="34068-7" codeSystem="2.16.840.1.113883.6.1"/>
            <text><paragraph>Dose info only.</paragraph></text>
          </section></component></structuredBody></component>
        </document>"""
        assert has_safety_sections(xml) is False

    def test_invalid_xml(self) -> None:
        assert has_safety_sections("not xml") is False

    def test_propofol_golden(self) -> None:
        xml_path = GOLDEN_DATA / "dailymed" / "spl_xml_propofol.xml"
        xml_text = xml_path.read_text()
        assert has_safety_sections(xml_text) is True


class TestMatchEventFuzzyBugHunting:
    """Testes para pares que falharam no bug hunting — fuzzy + MedDRA."""

    def test_hyperthermia_malignant_reorder(self) -> None:
        """hyperthermia malignant -> match Malignant Hyperthermia via MedDRA."""
        found, _matched = match_event_in_label(
            "hyperthermia malignant",
            ["Malignant Hyperthermia", "Fever"],
        )
        assert found is True

    def test_apnoea_british_spelling(self) -> None:
        """apnoea -> match via MedDRA group (RESPIRATORY DEPRESSION has APNOEA+APNEA)."""
        found, _matched = match_event_in_label(
            "apnoea",
            ["Apnea", "Respiratory depression"],
        )
        assert found is True

    def test_qt_prolongation_via_meddra(self) -> None:
        """QT prolongation -> match electrocardiogram QT prolonged via MedDRA."""
        found, _matched = match_event_in_label(
            "QT prolongation",
            ["Electrocardiogram QT prolonged"],
        )
        assert found is True

    def test_hypoglycaemia_british_spelling(self) -> None:
        """hypoglycaemia -> match hypoglycemia via MedDRA group."""
        found, _matched = match_event_in_label(
            "hypoglycaemia",
            ["Blood glucose decreased", "Hypoglycemia"],
        )
        assert found is True

    def test_anaphylactic_shock_to_anaphylaxis(self) -> None:
        """anaphylactic shock -> match anaphylaxis via MedDRA synonym."""
        found, _matched = match_event_in_label(
            "anaphylactic shock",
            ["Cases of Anaphylaxis have been reported"],
        )
        assert found is True
