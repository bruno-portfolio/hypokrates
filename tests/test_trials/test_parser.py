"""Testes para hypokrates.trials.parser."""

from __future__ import annotations

from hypokrates.trials.parser import build_trial, count_active, parse_studies
from tests.helpers import load_golden


class TestParseStudies:
    """parse_studies — total count e lista de trials."""

    def test_propofol_hypotension(self) -> None:
        data = load_golden("trials", "studies_propofol_hypotension.json")
        total_count, trials = parse_studies(data)

        assert total_count == 3
        assert len(trials) == 3
        assert trials[0].nct_id == "NCT05001234"

    def test_empty_response(self) -> None:
        total_count, trials = parse_studies({"totalCount": 0, "studies": []})
        assert total_count == 0
        assert trials == []

    def test_missing_fields(self) -> None:
        total_count, trials = parse_studies({})
        assert total_count == 0
        assert trials == []


class TestBuildTrial:
    """build_trial — constrói ClinicalTrial."""

    def test_full_study(self) -> None:
        data = load_golden("trials", "studies_propofol_hypotension.json")
        study = data["studies"][0]
        trial = build_trial(study)

        assert trial is not None
        assert trial.nct_id == "NCT05001234"
        assert trial.title == "Propofol vs Ketamine: Hemodynamic Effects"
        assert trial.status == "RECRUITING"
        assert trial.phase == "PHASE3"
        assert "Hypotension" in trial.conditions
        assert "Propofol" in trial.interventions

    def test_missing_nct_id(self) -> None:
        study = {"protocolSection": {"identificationModule": {}}}
        trial = build_trial(study)
        assert trial is None

    def test_empty_study(self) -> None:
        trial = build_trial({})
        assert trial is None

    def test_no_phase(self) -> None:
        study = {
            "protocolSection": {
                "identificationModule": {"nctId": "NCT001", "briefTitle": "Test"},
                "statusModule": {"overallStatus": "COMPLETED"},
                "designModule": {},
            }
        }
        trial = build_trial(study)
        assert trial is not None
        assert trial.phase == ""


class TestCountActive:
    """count_active — conta trials ativos."""

    def test_propofol_hypotension(self) -> None:
        data = load_golden("trials", "studies_propofol_hypotension.json")
        _, trials = parse_studies(data)
        active = count_active(trials)

        # RECRUITING + ACTIVE_NOT_RECRUITING = 2 (COMPLETED não conta)
        assert active == 2

    def test_all_completed(self) -> None:
        from hypokrates.trials.models import ClinicalTrial

        trials = [ClinicalTrial(nct_id="NCT001", status="COMPLETED")]
        assert count_active(trials) == 0

    def test_empty(self) -> None:
        assert count_active([]) == 0


class TestParseStudiesTotalCountFallback:
    """Bug 9: totalCount=0 com studies presentes."""

    def test_zero_total_count_with_studies(self) -> None:
        """totalCount=0 but studies present → use len(studies)."""
        data = {
            "totalCount": 0,
            "studies": [
                {
                    "protocolSection": {
                        "identificationModule": {
                            "nctId": "NCT001",
                            "briefTitle": "Test Trial 1",
                        },
                        "statusModule": {"overallStatus": "RECRUITING"},
                    }
                },
                {
                    "protocolSection": {
                        "identificationModule": {
                            "nctId": "NCT002",
                            "briefTitle": "Test Trial 2",
                        },
                        "statusModule": {"overallStatus": "COMPLETED"},
                    }
                },
                {
                    "protocolSection": {
                        "identificationModule": {
                            "nctId": "NCT003",
                            "briefTitle": "Test Trial 3",
                        },
                        "statusModule": {"overallStatus": "ACTIVE_NOT_RECRUITING"},
                    }
                },
            ],
        }
        total_count, trials = parse_studies(data)
        assert total_count == 3
        assert len(trials) == 3

    def test_zero_total_count_zero_studies(self) -> None:
        """totalCount=0 and no studies → remain 0."""
        total_count, trials = parse_studies({"totalCount": 0, "studies": []})
        assert total_count == 0
        assert trials == []

    def test_nonzero_total_count_preserved(self) -> None:
        """When totalCount is provided and > 0, use it as-is."""
        data = load_golden("trials", "studies_propofol_hypotension.json")
        total_count, trials = parse_studies(data)
        assert total_count == 3
        assert len(trials) == 3
