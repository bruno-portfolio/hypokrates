"""Testes para hypokrates.faers.parser — domínio médico como contrato.

Filosofia: cada campo clínico tem teste explícito provando que o valor está
correto. Golden data é o contrato — se o parser mudar output, o teste quebra
intencionalmente. Qualquer mudança no parser que altere o output precisa ser
uma decisão consciente (atualizar o teste) e não acidental.
"""

from __future__ import annotations

from typing import Any

import pytest

from hypokrates.faers.parser import parse_count_results, parse_reports
from hypokrates.models import Sex
from tests.helpers import make_raw_drug, make_raw_patient, make_raw_reaction, make_raw_report

# ---------------------------------------------------------------------------
# Contrato de campos clínicos — golden data como verdade
# ---------------------------------------------------------------------------


class TestParseReportsContract:
    """Golden data como contrato — se o output mudar, o teste quebra.

    Esses testes validam que o parser produz exatamente o output esperado
    para os dados congelados. Qualquer mudança no parser que altere o output
    precisa ser uma decisão consciente.
    """

    def test_parses_all_three_reports(self, golden_faers_adverse_events: dict[str, Any]) -> None:
        reports = parse_reports(golden_faers_adverse_events["results"])
        assert len(reports) == 3

    def test_report_id_is_string(self, golden_faers_adverse_events: dict[str, Any]) -> None:
        """safetyreportid sempre string, mesmo que venha como int."""
        reports = parse_reports(golden_faers_adverse_events["results"])
        assert reports[0].safety_report_id == "10001234"
        assert isinstance(reports[0].safety_report_id, str)

    def test_reaction_term_exact_match(self, golden_faers_adverse_events: dict[str, Any]) -> None:
        """HYPOTENSION não virou HYPERTENSION — contrato de termo clínico."""
        reports = parse_reports(golden_faers_adverse_events["results"])
        terms = [r.term for r in reports[0].reactions]
        assert terms == ["HYPOTENSION", "BRADYCARDIA"]

    def test_reaction_outcome_maps_correctly(
        self, golden_faers_adverse_events: dict[str, Any]
    ) -> None:
        """outcome '1' → 'recovered', não outro valor."""
        reports = parse_reports(golden_faers_adverse_events["results"])
        for reaction in reports[0].reactions:
            assert reaction.outcome == "recovered"

    def test_patient_age_preserves_precision(
        self, golden_faers_adverse_events: dict[str, Any]
    ) -> None:
        """65 não virou 6.5 — preservação de valor numérico."""
        reports = parse_reports(golden_faers_adverse_events["results"])
        assert reports[0].patient.age == 65.0

    def test_patient_sex_code_maps_correctly(
        self, golden_faers_adverse_events: dict[str, Any]
    ) -> None:
        """código '1' → Sex.MALE, '2' → Sex.FEMALE."""
        reports = parse_reports(golden_faers_adverse_events["results"])
        assert reports[0].patient.sex == Sex.MALE
        assert reports[1].patient.sex == Sex.FEMALE
        assert reports[2].patient.sex == Sex.MALE

    def test_patient_weight_preserves_value(
        self, golden_faers_adverse_events: dict[str, Any]
    ) -> None:
        """80.0 kg preservado com unidade."""
        reports = parse_reports(golden_faers_adverse_events["results"])
        assert reports[0].patient.weight == 80.0
        assert reports[0].patient.weight_unit == "kg"

    def test_drug_name_from_openfda(self, golden_faers_adverse_events: dict[str, Any]) -> None:
        """openfda.generic_name[0] é a fonte correta do nome."""
        reports = parse_reports(golden_faers_adverse_events["results"])
        assert reports[0].drugs[0].name == "PROPOFOL"

    def test_drug_role_preserved(self, golden_faers_adverse_events: dict[str, Any]) -> None:
        """drugcharacterization '1' = primary suspect."""
        reports = parse_reports(golden_faers_adverse_events["results"])
        assert reports[0].drugs[0].role == "1"

    def test_drug_dose_preserved(self, golden_faers_adverse_events: dict[str, Any]) -> None:
        """Dose text preservada fielmente."""
        reports = parse_reports(golden_faers_adverse_events["results"])
        assert reports[0].drugs[0].dose == "200 MG, IV"

    def test_drug_indication_preserved(self, golden_faers_adverse_events: dict[str, Any]) -> None:
        reports = parse_reports(golden_faers_adverse_events["results"])
        assert reports[0].drugs[0].indication == "ANAESTHESIA"

    def test_serious_reasons_collected(self, golden_faers_adverse_events: dict[str, Any]) -> None:
        """Report 1: hospitalization. Report 2: life_threatening."""
        reports = parse_reports(golden_faers_adverse_events["results"])
        assert reports[0].serious_reasons == ["hospitalization"]
        assert reports[1].serious_reasons == ["life_threatening"]

    def test_country_preserved(self, golden_faers_adverse_events: dict[str, Any]) -> None:
        """País do report preservado."""
        reports = parse_reports(golden_faers_adverse_events["results"])
        assert reports[0].country == "US"
        assert reports[1].country == "BR"
        assert reports[2].country == "JP"

    def test_non_serious_report(self, golden_faers_adverse_events: dict[str, Any]) -> None:
        """Report 3: serious='2' → False."""
        reports = parse_reports(golden_faers_adverse_events["results"])
        assert reports[2].serious is False
        assert reports[2].serious_reasons == []

    def test_receive_date_preserved(self, golden_faers_adverse_events: dict[str, Any]) -> None:
        reports = parse_reports(golden_faers_adverse_events["results"])
        assert reports[0].receive_date == "20240101"
        assert reports[0].receipt_date == "20240105"

    def test_source_type_from_primarysource(
        self, golden_faers_adverse_events: dict[str, Any]
    ) -> None:
        reports = parse_reports(golden_faers_adverse_events["results"])
        assert reports[0].source_type == "1"
        assert reports[2].source_type == "3"

    def test_multiple_drugs_report(self, golden_faers_adverse_events: dict[str, Any]) -> None:
        """Report 3: propofol (primary) + fentanyl (secondary)."""
        reports = parse_reports(golden_faers_adverse_events["results"])
        drugs = reports[2].drugs
        assert len(drugs) == 2
        assert drugs[0].name == "PROPOFOL"
        assert drugs[0].role == "1"
        assert drugs[1].name == "FENTANYL"
        assert drugs[1].role == "2"

    def test_meddra_version_preserved(self, golden_faers_adverse_events: dict[str, Any]) -> None:
        """MedDRA version '27.1' mantido."""
        reports = parse_reports(golden_faers_adverse_events["results"])
        assert reports[0].reactions[0].version == "27.1"

    def test_second_report_outcome_recovering(
        self, golden_faers_adverse_events: dict[str, Any]
    ) -> None:
        """Report 2: outcome '2' → 'recovering'."""
        reports = parse_reports(golden_faers_adverse_events["results"])
        assert reports[1].reactions[0].outcome == "recovering"

    def test_patient_without_weight_has_none(
        self, golden_faers_adverse_events: dict[str, Any]
    ) -> None:
        """Report 2: sem peso → None."""
        reports = parse_reports(golden_faers_adverse_events["results"])
        assert reports[1].patient.weight is None
        assert reports[1].patient.weight_unit is None

    def test_age_unit_preserved(self, golden_faers_adverse_events: dict[str, Any]) -> None:
        """age_unit '801' (years) preservado."""
        reports = parse_reports(golden_faers_adverse_events["results"])
        assert reports[0].patient.age_unit == "801"

    def test_handles_empty_list(self) -> None:
        reports = parse_reports([])
        assert reports == []


# ---------------------------------------------------------------------------
# Determinismo — mesmo input, mesmo output, sempre
# ---------------------------------------------------------------------------


class TestParseReportsDeterminism:
    """Determinismo — mesmo input, mesmo output, sempre.

    Roda o parser 100x com o mesmo golden data e verifica que o output
    é idêntico em todas as runs. Pega dict ordering, timestamps de
    processamento vazando no output, ou qualquer non-determinism.
    """

    def test_parse_reports_deterministic_100x(
        self, golden_faers_adverse_events: dict[str, Any]
    ) -> None:
        raw = golden_faers_adverse_events["results"]
        baseline = parse_reports(raw)
        baseline_dicts = [r.model_dump() for r in baseline]

        for i in range(99):
            result = parse_reports(raw)
            result_dicts = [r.model_dump() for r in result]
            assert result_dicts == baseline_dicts, f"Non-determinism na iteração {i + 2}"

    def test_parse_count_results_deterministic(
        self, golden_faers_top_events: dict[str, Any]
    ) -> None:
        raw = golden_faers_top_events["results"]
        baseline = parse_count_results(raw)
        baseline_dicts = [e.model_dump() for e in baseline]

        for i in range(99):
            result = parse_count_results(raw)
            result_dicts = [e.model_dump() for e in result]
            assert result_dicts == baseline_dicts, f"Non-determinism na iteração {i + 2}"


# ---------------------------------------------------------------------------
# Contrato de contagem — ordem e valores exatos
# ---------------------------------------------------------------------------


class TestParseCountResultsContract:
    """Contrato de contagem — ordem e valores exatos."""

    def test_parses_all_ten_terms(self, golden_faers_top_events: dict[str, Any]) -> None:
        events = parse_count_results(golden_faers_top_events["results"])
        assert len(events) == 10

    def test_terms_in_order(self, golden_faers_top_events: dict[str, Any]) -> None:
        """DEATH primeiro (maior count)."""
        events = parse_count_results(golden_faers_top_events["results"])
        assert events[0].term == "DEATH"
        assert events[-1].term == "DRUG INEFFECTIVE"

    def test_counts_are_integers(self, golden_faers_top_events: dict[str, Any]) -> None:
        """5234 não virou '5234'."""
        events = parse_count_results(golden_faers_top_events["results"])
        assert events[0].count == 5234
        assert isinstance(events[0].count, int)

    def test_all_terms_present(self, golden_faers_top_events: dict[str, Any]) -> None:
        """Todos os 10 termos com count > 0."""
        events = parse_count_results(golden_faers_top_events["results"])
        expected_terms = [
            "DEATH",
            "CARDIAC ARREST",
            "HYPOTENSION",
            "BRADYCARDIA",
            "PROPOFOL INFUSION SYNDROME",
            "RESPIRATORY DEPRESSION",
            "NAUSEA",
            "INJECTION SITE PAIN",
            "APNOEA",
            "DRUG INEFFECTIVE",
        ]
        actual_terms = [e.term for e in events]
        assert actual_terms == expected_terms
        assert all(e.count > 0 for e in events)

    def test_handles_empty_results(self) -> None:
        events = parse_count_results([])
        assert events == []

    def test_skips_empty_term(self) -> None:
        """Itens com term vazio são ignorados."""
        events = parse_count_results([{"term": "", "count": 100}, {"term": "NAUSEA", "count": 50}])
        assert len(events) == 1
        assert events[0].term == "NAUSEA"

    def test_skips_non_string_term(self) -> None:
        """term não-string ignorado."""
        events = parse_count_results([{"term": 123, "count": 100}])
        assert len(events) == 0


# ---------------------------------------------------------------------------
# Dados demográficos — edge cases reais do FAERS
# ---------------------------------------------------------------------------


class TestParseReportsDemographics:
    """Parsing de dados demográficos — edge cases reais do FAERS."""

    @pytest.mark.parametrize(
        ("sex_code", "expected_sex"),
        [
            ("1", Sex.MALE),
            ("2", Sex.FEMALE),
            ("0", Sex.UNKNOWN),
        ],
    )
    def test_sex_code_mapping(self, sex_code: str, expected_sex: Sex) -> None:
        raw = [make_raw_report(patient=make_raw_patient(sex=sex_code))]
        reports = parse_reports(raw)
        assert reports[0].patient.sex == expected_sex

    def test_invalid_sex_code_maps_to_unknown(self) -> None:
        """Código inválido '99' → UNK."""
        raw = [make_raw_report(patient=make_raw_patient(sex="99"))]
        reports = parse_reports(raw)
        assert reports[0].patient.sex == Sex.UNKNOWN

    def test_missing_sex_maps_to_unknown(self) -> None:
        """Sem patientsex → padrão UNK (código '0')."""
        raw = [make_raw_report(patient=make_raw_patient(sex=None))]
        reports = parse_reports(raw)
        assert reports[0].patient.sex == Sex.UNKNOWN

    @pytest.mark.parametrize(
        ("age_raw", "expected_age"),
        [
            ("65", 65.0),
            ("65.5", 65.5),
            ("0", 0.0),
            ("120", 120.0),
            ("0.5", 0.5),
        ],
    )
    def test_valid_age_parsed(self, age_raw: str, expected_age: float) -> None:
        raw = [make_raw_report(patient=make_raw_patient(age=age_raw))]
        reports = parse_reports(raw)
        assert reports[0].patient.age == expected_age

    def test_non_numeric_age_becomes_none(self) -> None:
        """'abc' não é conversível → None."""
        raw = [make_raw_report(patient=make_raw_patient(age="abc"))]
        reports = parse_reports(raw)
        assert reports[0].patient.age is None

    def test_missing_age_becomes_none(self) -> None:
        raw = [make_raw_report(patient=make_raw_patient(age=None))]
        reports = parse_reports(raw)
        assert reports[0].patient.age is None

    def test_age_unit_preserved(self) -> None:
        raw = [make_raw_report(patient=make_raw_patient(age_unit="801"))]
        reports = parse_reports(raw)
        assert reports[0].patient.age_unit == "801"

    def test_missing_age_unit(self) -> None:
        raw = [make_raw_report(patient=make_raw_patient(age_unit=None))]
        reports = parse_reports(raw)
        assert reports[0].patient.age_unit is None

    @pytest.mark.parametrize(
        ("weight_raw", "expected_weight"),
        [
            ("80.0", 80.0),
            ("0.5", 0.5),
            ("120", 120.0),
        ],
    )
    def test_valid_weight_parsed(self, weight_raw: str, expected_weight: float) -> None:
        raw = [make_raw_report(patient=make_raw_patient(weight=weight_raw))]
        reports = parse_reports(raw)
        assert reports[0].patient.weight == expected_weight
        assert reports[0].patient.weight_unit == "kg"

    def test_non_numeric_weight_becomes_none(self) -> None:
        raw = [make_raw_report(patient=make_raw_patient(weight="abc"))]
        reports = parse_reports(raw)
        assert reports[0].patient.weight is None
        assert reports[0].patient.weight_unit is None

    def test_missing_weight_becomes_none(self) -> None:
        raw = [make_raw_report(patient=make_raw_patient(weight=None))]
        reports = parse_reports(raw)
        assert reports[0].patient.weight is None

    def test_golden_demographics_newborn(self, golden_faers_demographics: dict[str, Any]) -> None:
        """Idade 0 (recém-nascido) parseada corretamente."""
        reports = parse_reports(golden_faers_demographics["results"])
        assert reports[0].patient.age == 0.0
        assert reports[0].patient.weight == 3.5

    def test_golden_demographics_centenarian(
        self, golden_faers_demographics: dict[str, Any]
    ) -> None:
        """Idade 120 (centenário) parseada corretamente."""
        reports = parse_reports(golden_faers_demographics["results"])
        assert reports[1].patient.age == 120.0

    def test_golden_demographics_missing_age(
        self, golden_faers_demographics: dict[str, Any]
    ) -> None:
        """Sem idade → None."""
        reports = parse_reports(golden_faers_demographics["results"])
        assert reports[2].patient.age is None

    def test_golden_demographics_abc_age(self, golden_faers_demographics: dict[str, Any]) -> None:
        """Idade 'abc' → None."""
        reports = parse_reports(golden_faers_demographics["results"])
        assert reports[3].patient.age is None

    def test_golden_demographics_sex_unknown_code(
        self, golden_faers_demographics: dict[str, Any]
    ) -> None:
        """Sexo código '0' → UNK."""
        reports = parse_reports(golden_faers_demographics["results"])
        assert reports[5].patient.sex == Sex.UNKNOWN

    def test_golden_demographics_sex_invalid_code(
        self, golden_faers_demographics: dict[str, Any]
    ) -> None:
        """Sexo código '99' → UNK."""
        reports = parse_reports(golden_faers_demographics["results"])
        assert reports[6].patient.sex == Sex.UNKNOWN

    def test_golden_demographics_sex_missing(
        self, golden_faers_demographics: dict[str, Any]
    ) -> None:
        """Sem patientsex → UNK."""
        reports = parse_reports(golden_faers_demographics["results"])
        # DEMO008 has no patientsex
        assert reports[7].patient.sex == Sex.UNKNOWN


# ---------------------------------------------------------------------------
# Parsing de drogas — fallback chain e polifarmácia
# ---------------------------------------------------------------------------


class TestParseReportsDrugs:
    """Parsing de drogas — fallback chain e polifarmácia."""

    def test_drug_name_from_openfda(self) -> None:
        """openfda.generic_name[0] é a fonte primária."""
        raw = [
            make_raw_report(
                patient=make_raw_patient(
                    drugs=[make_raw_drug(name="PROPOFOL_MED", generic_names=["PROPOFOL_GENERIC"])]
                )
            )
        ]
        reports = parse_reports(raw)
        assert reports[0].drugs[0].name == "PROPOFOL_GENERIC"

    def test_drug_name_fallback_to_medicinalproduct(self) -> None:
        """Sem openfda → usa medicinalproduct."""
        raw = [
            make_raw_report(
                patient=make_raw_patient(
                    drugs=[make_raw_drug(name="KETAMINE", include_openfda=False)]
                )
            )
        ]
        reports = parse_reports(raw)
        assert reports[0].drugs[0].name == "KETAMINE"

    def test_drug_name_fallback_empty_generic_name(self) -> None:
        """openfda.generic_name=[] → fallback para medicinalproduct."""
        raw = [
            make_raw_report(
                patient=make_raw_patient(drugs=[make_raw_drug(name="KETAMINE", generic_names=[])])
            )
        ]
        reports = parse_reports(raw)
        assert reports[0].drugs[0].name == "KETAMINE"

    def test_drug_without_openfda_nor_medicinal(self) -> None:
        """Sem openfda nem medicinalproduct → 'Unknown'."""
        drug: dict[str, Any] = {"drugcharacterization": "1"}
        raw = [make_raw_report(patient=make_raw_patient(drugs=[drug]))]
        reports = parse_reports(raw)
        assert reports[0].drugs[0].name == "Unknown"

    def test_multiple_drugs_all_parsed(self, golden_faers_multi_drug: dict[str, Any]) -> None:
        """5 drogas → 5 FAERSDrug."""
        reports = parse_reports(golden_faers_multi_drug["results"])
        assert len(reports[0].drugs) == 5

    @pytest.mark.parametrize(
        ("role_code", "description"),
        [
            ("1", "primary suspect"),
            ("2", "secondary suspect"),
            ("3", "concomitant"),
            ("4", "interacting"),
        ],
    )
    def test_drug_roles_all_types(
        self, golden_faers_multi_drug: dict[str, Any], role_code: str, description: str
    ) -> None:
        """Todos os roles de droga preservados."""
        reports = parse_reports(golden_faers_multi_drug["results"])
        roles = [d.role for d in reports[0].drugs]
        assert role_code in roles, f"Role {role_code} ({description}) não encontrado"

    def test_drug_route_preserved(self) -> None:
        raw = [make_raw_report(patient=make_raw_patient(drugs=[make_raw_drug(route="065")]))]
        reports = parse_reports(raw)
        assert reports[0].drugs[0].route == "065"

    def test_drug_indication_preserved(self) -> None:
        raw = [
            make_raw_report(patient=make_raw_patient(drugs=[make_raw_drug(indication="SEDATION")]))
        ]
        reports = parse_reports(raw)
        assert reports[0].drugs[0].indication == "SEDATION"


# ---------------------------------------------------------------------------
# Parsing de reações — MedDRA terms e outcomes
# ---------------------------------------------------------------------------


class TestParseReportsReactions:
    """Parsing de reações — MedDRA terms e outcomes."""

    @pytest.mark.parametrize(
        ("outcome_code", "expected_outcome"),
        [
            ("1", "recovered"),
            ("2", "recovering"),
            ("3", "not_recovered"),
            ("4", "recovered_with_sequelae"),
            ("5", "fatal"),
            ("6", "unknown"),
        ],
    )
    def test_outcome_code_mapping(self, outcome_code: str, expected_outcome: str) -> None:
        raw = [
            make_raw_report(
                patient=make_raw_patient(reactions=[make_raw_reaction(outcome=outcome_code)])
            )
        ]
        reports = parse_reports(raw)
        assert reports[0].reactions[0].outcome == expected_outcome

    def test_unknown_outcome_code_maps_to_none(self) -> None:
        """Outcome '0' ou '99' → None (não está no OUTCOME_MAP)."""
        raw = [
            make_raw_report(patient=make_raw_patient(reactions=[make_raw_reaction(outcome="99")]))
        ]
        reports = parse_reports(raw)
        assert reports[0].reactions[0].outcome is None

    def test_missing_outcome_maps_to_none(self) -> None:
        raw = [
            make_raw_report(patient=make_raw_patient(reactions=[make_raw_reaction(outcome=None)]))
        ]
        reports = parse_reports(raw)
        assert reports[0].reactions[0].outcome is None

    def test_empty_term_skipped(self) -> None:
        """Reação sem termo ignorada."""
        raw = [
            make_raw_report(
                patient=make_raw_patient(
                    reactions=[
                        make_raw_reaction(term=""),
                        make_raw_reaction(term="NAUSEA"),
                    ]
                )
            )
        ]
        reports = parse_reports(raw)
        assert len(reports[0].reactions) == 1
        assert reports[0].reactions[0].term == "NAUSEA"

    def test_meddra_version_preserved(self) -> None:
        raw = [
            make_raw_report(
                patient=make_raw_patient(reactions=[make_raw_reaction(version="27.1")])
            )
        ]
        reports = parse_reports(raw)
        assert reports[0].reactions[0].version == "27.1"

    def test_multiple_reactions_order_preserved(self) -> None:
        raw = [
            make_raw_report(
                patient=make_raw_patient(
                    reactions=[
                        make_raw_reaction(term="DEATH"),
                        make_raw_reaction(term="CARDIAC ARREST"),
                        make_raw_reaction(term="HYPOTENSION"),
                    ]
                )
            )
        ]
        reports = parse_reports(raw)
        terms = [r.term for r in reports[0].reactions]
        assert terms == ["DEATH", "CARDIAC ARREST", "HYPOTENSION"]


# ---------------------------------------------------------------------------
# Seriousness flags — combinações reais
# ---------------------------------------------------------------------------


class TestParseReportsSerious:
    """Seriousness flags — combinações reais."""

    def test_all_six_flags(self, golden_faers_serious_all: dict[str, Any]) -> None:
        """6 flags '1' → 6 reasons."""
        reports = parse_reports(golden_faers_serious_all["results"])
        r = reports[0]
        assert r.serious is True
        expected = [
            "death",
            "hospitalization",
            "life_threatening",
            "disability",
            "congenital_anomaly",
            "other",
        ]
        assert r.serious_reasons == expected

    def test_non_serious_report(self, golden_faers_serious_all: dict[str, Any]) -> None:
        """serious='2' → False, sem reasons."""
        reports = parse_reports(golden_faers_serious_all["results"])
        r = reports[1]
        assert r.serious is False
        assert r.serious_reasons == []

    def test_serious_without_specific_flags(
        self, golden_faers_serious_all: dict[str, Any]
    ) -> None:
        """serious='1' mas sem flags específicos → True, reasons=[]."""
        reports = parse_reports(golden_faers_serious_all["results"])
        r = reports[2]
        assert r.serious is True
        assert r.serious_reasons == []

    def test_flag_value_not_one_ignored(self) -> None:
        """Flag='2' NÃO adiciona reason."""
        raw = [
            make_raw_report(
                seriousness_flags={
                    "seriousnessdeath": "2",
                    "seriousnesshospitalization": "1",
                }
            )
        ]
        reports = parse_reports(raw)
        assert reports[0].serious_reasons == ["hospitalization"]

    def test_flag_value_zero_ignored(self) -> None:
        """Flag='0' NÃO adiciona reason."""
        raw = [
            make_raw_report(
                seriousness_flags={
                    "seriousnessdeath": "0",
                    "seriousnesshospitalization": "0",
                }
            )
        ]
        reports = parse_reports(raw)
        assert reports[0].serious_reasons == []

    def test_individual_flag_hospitalization(self) -> None:
        raw = [make_raw_report(seriousness_flags={"seriousnesshospitalization": "1"})]
        reports = parse_reports(raw)
        assert "hospitalization" in reports[0].serious_reasons

    def test_individual_flag_death(self) -> None:
        raw = [make_raw_report(seriousness_flags={"seriousnessdeath": "1"})]
        reports = parse_reports(raw)
        assert "death" in reports[0].serious_reasons

    def test_individual_flag_life_threatening(self) -> None:
        raw = [make_raw_report(seriousness_flags={"seriousnesslifethreatening": "1"})]
        reports = parse_reports(raw)
        assert "life_threatening" in reports[0].serious_reasons

    def test_individual_flag_disability(self) -> None:
        raw = [make_raw_report(seriousness_flags={"seriousnessdisabling": "1"})]
        reports = parse_reports(raw)
        assert "disability" in reports[0].serious_reasons

    def test_individual_flag_congenital(self) -> None:
        raw = [make_raw_report(seriousness_flags={"seriousnesscongenitalanomali": "1"})]
        reports = parse_reports(raw)
        assert "congenital_anomaly" in reports[0].serious_reasons

    def test_individual_flag_other(self) -> None:
        raw = [make_raw_report(seriousness_flags={"seriousnessother": "1"})]
        reports = parse_reports(raw)
        assert "other" in reports[0].serious_reasons
