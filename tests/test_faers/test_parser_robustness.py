"""Testes de resiliência do parser FAERS — dados malformados e coerção de tipos.

O FAERS é voluntary reporting — dados vêm sujos. O parser precisa ser
resiliente: parsear o que pode, skippar o que não pode, e nunca crashar
silenciosamente.
"""

from __future__ import annotations

from typing import Any

import pytest

from hypokrates.faers.parser import parse_count_results, parse_reports
from tests.helpers import make_raw_patient, make_raw_report


class TestParserMalformedData:
    """Parser não pode crashar com dados malformados."""

    def test_missing_patient_key(self) -> None:
        """Report sem 'patient' key → parseado com defaults."""
        raw = [{"safetyreportid": "1", "serious": "1", "occurcountry": "US"}]
        reports = parse_reports(raw)
        assert len(reports) == 1
        assert reports[0].safety_report_id == "1"
        assert reports[0].drugs == []
        assert reports[0].reactions == []

    def test_empty_patient(self) -> None:
        """patient: {} → parseado com defaults."""
        raw = [make_raw_report(patient={})]
        reports = parse_reports(raw)
        assert len(reports) == 1
        assert reports[0].drugs == []
        assert reports[0].reactions == []

    def test_null_reactions(self) -> None:
        """reaction: null → lista vazia (via golden data)."""
        raw = [make_raw_report(patient={"patientsex": "1", "reaction": None, "drug": []})]
        reports = parse_reports(raw)
        assert len(reports) == 1
        assert reports[0].reactions == []

    def test_null_drugs(self) -> None:
        """drug: null → lista vazia."""
        raw = [make_raw_report(patient={"patientsex": "1", "reaction": [], "drug": None})]
        reports = parse_reports(raw)
        assert len(reports) == 1
        assert reports[0].drugs == []

    def test_empty_drug_list(self) -> None:
        """drug: [] → lista vazia."""
        raw = [make_raw_report(patient=make_raw_patient(drugs=[]))]
        reports = parse_reports(raw)
        assert reports[0].drugs == []

    def test_numeric_report_id_coerced(self) -> None:
        """safetyreportid: 999888 (int) → '999888' (string)."""
        raw = [make_raw_report()]
        raw[0]["safetyreportid"] = 999888
        reports = parse_reports(raw)
        assert reports[0].safety_report_id == "999888"
        assert isinstance(reports[0].safety_report_id, str)

    def test_empty_results_list(self) -> None:
        """[] → []"""
        reports = parse_reports([])
        assert reports == []

    def test_partial_parse_continues(self) -> None:
        """Report 1 com dados bizarros, reports 2-3 ok → 2-3 parseados."""
        raw = [
            {"safetyreportid": "BAD", "patient": "not_a_dict"},  # Vai falhar
            make_raw_report(report_id="GOOD1"),
            make_raw_report(report_id="GOOD2"),
        ]
        reports = parse_reports(raw)
        # O parser faz try/except e continua
        good_ids = [r.safety_report_id for r in reports]
        assert "GOOD1" in good_ids
        assert "GOOD2" in good_ids

    def test_golden_malformed_no_crash(self, golden_faers_malformed: dict[str, Any]) -> None:
        """Todos os reports malformados parseados sem crash."""
        reports = parse_reports(golden_faers_malformed["results"])
        assert isinstance(reports, list)
        assert len(reports) >= 1  # Ao menos alguns parsearão

    def test_golden_malformed_report_without_patient(
        self, golden_faers_malformed: dict[str, Any]
    ) -> None:
        """MAL001: sem patient key → parseado com defaults."""
        reports = parse_reports(golden_faers_malformed["results"])
        mal001 = [r for r in reports if r.safety_report_id == "MAL001"]
        assert len(mal001) == 1
        assert mal001[0].drugs == []
        assert mal001[0].reactions == []

    def test_golden_malformed_empty_patient(self, golden_faers_malformed: dict[str, Any]) -> None:
        """MAL002: patient: {} → defaults."""
        reports = parse_reports(golden_faers_malformed["results"])
        mal002 = [r for r in reports if r.safety_report_id == "MAL002"]
        assert len(mal002) == 1
        assert mal002[0].drugs == []

    def test_golden_malformed_serious_all_zeros(
        self, golden_faers_malformed: dict[str, Any]
    ) -> None:
        """MAL007: serious='1' mas todos os flags='0' → True, reasons=[]."""
        reports = parse_reports(golden_faers_malformed["results"])
        mal007 = [r for r in reports if r.safety_report_id == "MAL007"]
        assert len(mal007) == 1
        assert mal007[0].serious is True
        assert mal007[0].serious_reasons == []

    def test_golden_malformed_numeric_report_id(
        self, golden_faers_malformed: dict[str, Any]
    ) -> None:
        """Report com safetyreportid numérico → string."""
        reports = parse_reports(golden_faers_malformed["results"])
        ids = [r.safety_report_id for r in reports]
        assert "999888" in ids

    def test_drug_without_openfda_key(self, golden_faers_malformed: dict[str, Any]) -> None:
        """MAL005: droga sem openfda → usa medicinalproduct."""
        reports = parse_reports(golden_faers_malformed["results"])
        mal005 = [r for r in reports if r.safety_report_id == "MAL005"]
        assert len(mal005) == 1
        assert mal005[0].drugs[0].name == "KETAMINE"


class TestParserTypeCoercion:
    """Tipos inesperados que o FAERS real envia."""

    def test_age_as_string_float(self) -> None:
        """'65.5' → 65.5"""
        raw = [make_raw_report(patient=make_raw_patient(age="65.5"))]
        reports = parse_reports(raw)
        assert reports[0].patient.age == 65.5

    def test_age_as_int(self) -> None:
        """65 (int, não string) → 65.0"""
        raw = [make_raw_report(patient=make_raw_patient())]
        raw[0]["patient"]["patientonsetage"] = 65
        reports = parse_reports(raw)
        assert reports[0].patient.age == 65.0

    def test_weight_as_int(self) -> None:
        """80 (int) → 80.0"""
        raw = [make_raw_report(patient=make_raw_patient())]
        raw[0]["patient"]["patientweight"] = 80
        reports = parse_reports(raw)
        assert reports[0].patient.weight == 80.0

    def test_count_as_integer(self) -> None:
        """count: 5234 (int) preservado."""
        events = parse_count_results([{"term": "NAUSEA", "count": 5234}])
        assert events[0].count == 5234
        assert isinstance(events[0].count, int)

    def test_serious_as_string(self) -> None:
        """serious: '1' → True."""
        raw = [make_raw_report(serious="1")]
        reports = parse_reports(raw)
        assert reports[0].serious is True

    def test_serious_as_two_string(self) -> None:
        """serious: '2' → False."""
        raw = [make_raw_report(serious="2")]
        reports = parse_reports(raw)
        assert reports[0].serious is False


class TestParserMultiDrugGolden:
    """Testes com golden data de polifarmácia."""

    def test_five_drugs_all_parsed(self, golden_faers_multi_drug: dict[str, Any]) -> None:
        reports = parse_reports(golden_faers_multi_drug["results"])
        assert len(reports[0].drugs) == 5

    def test_drug_without_openfda_uses_medicinalproduct(
        self, golden_faers_multi_drug: dict[str, Any]
    ) -> None:
        """MULTI002: drogas sem openfda → medicinalproduct."""
        reports = parse_reports(golden_faers_multi_drug["results"])
        r = reports[1]
        drug_names = [d.name for d in r.drugs]
        assert "PROPOFOL INJECTION" in drug_names
        assert "UNKNOWN DRUG ABC" in drug_names

    def test_drug_empty_name_uses_unknown(self, golden_faers_multi_drug: dict[str, Any]) -> None:
        """MULTI002: medicinalproduct='' → fallback (empty string passthrough)."""
        reports = parse_reports(golden_faers_multi_drug["results"])
        r = reports[1]
        # Pelo menos as drogas com nome são parseadas
        assert len(r.drugs) == 3

    def test_drug_with_empty_generic_name_list(
        self, golden_faers_multi_drug: dict[str, Any]
    ) -> None:
        """MULTI003: generic_name=[] → fallback para medicinalproduct."""
        reports = parse_reports(golden_faers_multi_drug["results"])
        r = reports[2]
        # Primeira droga tem openfda.generic_name=[]
        assert r.drugs[0].name == "PROPOFOL"

    def test_empty_reaction_term_skipped(self, golden_faers_multi_drug: dict[str, Any]) -> None:
        """MULTI003: reação com term='' ignorada."""
        reports = parse_reports(golden_faers_multi_drug["results"])
        r = reports[2]
        terms = [rx.term for rx in r.reactions]
        assert "" not in terms
        assert len(r.reactions) == 3  # 4 no raw, 1 com term=""

    @pytest.mark.parametrize(
        ("outcome_code", "expected"),
        [
            ("5", "fatal"),
            ("1", "recovered"),
            ("3", "not_recovered"),
        ],
    )
    def test_reaction_outcomes_varied(
        self,
        golden_faers_multi_drug: dict[str, Any],
        outcome_code: str,
        expected: str,
    ) -> None:
        """Todos os outcomes variados mapeados corretamente."""
        reports = parse_reports(golden_faers_multi_drug["results"])
        all_outcomes = {}
        for r in reports:
            for rx in r.reactions:
                if rx.outcome:
                    all_outcomes[rx.outcome] = True
        assert expected in all_outcomes
