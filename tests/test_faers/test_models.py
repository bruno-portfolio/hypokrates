"""Testes para hypokrates.faers.models — Pydantic models e serialização."""

from __future__ import annotations

from hypokrates.faers.models import FAERSDrug, FAERSReaction, FAERSReport, FAERSResult
from hypokrates.models import AdverseEvent, MetaInfo, PatientProfile, Sex


class TestFAERSReaction:
    """FAERSReaction — criação e defaults."""

    def test_create_minimal(self) -> None:
        r = FAERSReaction(term="HYPOTENSION")
        assert r.term == "HYPOTENSION"
        assert r.outcome is None
        assert r.version is None

    def test_create_full(self) -> None:
        r = FAERSReaction(term="NAUSEA", outcome="recovered", version="27.1")
        assert r.outcome == "recovered"
        assert r.version == "27.1"

    def test_serialization_roundtrip(self) -> None:
        r = FAERSReaction(term="NAUSEA", outcome="recovered", version="27.1")
        data = r.model_dump()
        r2 = FAERSReaction(**data)
        assert r == r2


class TestFAERSDrug:
    """FAERSDrug — criação, defaults e serialização."""

    def test_create_minimal(self) -> None:
        d = FAERSDrug(name="PROPOFOL")
        assert d.name == "PROPOFOL"
        assert d.role is None
        assert d.route is None
        assert d.dose is None
        assert d.indication is None

    def test_create_full(self) -> None:
        d = FAERSDrug(
            name="PROPOFOL", role="1", route="IV", dose="200mg", indication="ANAESTHESIA"
        )
        assert d.role == "1"
        assert d.indication == "ANAESTHESIA"

    def test_serialization_roundtrip(self) -> None:
        d = FAERSDrug(name="PROPOFOL", role="1", route="IV")
        data = d.model_dump()
        d2 = FAERSDrug(**data)
        assert d == d2


class TestFAERSReport:
    """FAERSReport — criação, defaults e composição."""

    def test_create_minimal(self) -> None:
        r = FAERSReport(safety_report_id="123")
        assert r.safety_report_id == "123"
        assert r.serious is False
        assert r.drugs == []
        assert r.reactions == []

    def test_defaults(self) -> None:
        r = FAERSReport(safety_report_id="456")
        assert r.serious_reasons == []
        assert r.country is None
        assert r.receive_date is None
        assert r.receipt_date is None
        assert r.source_type is None

    def test_patient_default(self) -> None:
        r = FAERSReport(safety_report_id="789")
        assert r.patient.sex == Sex.UNKNOWN
        assert r.patient.age is None

    def test_full_report_with_nested(self) -> None:
        r = FAERSReport(
            safety_report_id="999",
            serious=True,
            serious_reasons=["death", "hospitalization"],
            country="US",
            patient=PatientProfile(age=65.0, sex=Sex.MALE, weight=80.0),
            drugs=[FAERSDrug(name="PROPOFOL", role="1")],
            reactions=[FAERSReaction(term="HYPOTENSION", outcome="recovered")],
        )
        assert r.serious is True
        assert len(r.serious_reasons) == 2
        assert r.patient.age == 65.0
        assert r.drugs[0].name == "PROPOFOL"
        assert r.reactions[0].term == "HYPOTENSION"

    def test_serialization_roundtrip(self) -> None:
        r = FAERSReport(
            safety_report_id="123",
            serious=True,
            drugs=[FAERSDrug(name="PROPOFOL")],
            reactions=[FAERSReaction(term="NAUSEA")],
        )
        data = r.model_dump()
        r2 = FAERSReport(**data)
        assert r.safety_report_id == r2.safety_report_id
        assert r.drugs[0].name == r2.drugs[0].name


class TestFAERSResult:
    """FAERSResult — composição com MetaInfo."""

    def test_create_with_events(self) -> None:
        result = FAERSResult(
            events=[AdverseEvent(term="NAUSEA", count=100)],
            meta=MetaInfo(source="test"),
        )
        assert len(result.events) == 1
        assert result.events[0].count == 100

    def test_create_with_reports(self) -> None:
        result = FAERSResult(
            reports=[FAERSReport(safety_report_id="123")],
            meta=MetaInfo(source="OpenFDA/FAERS"),
        )
        assert len(result.reports) == 1
        assert result.meta.source == "OpenFDA/FAERS"

    def test_defaults_empty_lists(self) -> None:
        result = FAERSResult(meta=MetaInfo(source="test"))
        assert result.reports == []
        assert result.events == []
        assert result.drugs == []

    def test_meta_has_disclaimer(self) -> None:
        result = FAERSResult(meta=MetaInfo(source="test"))
        assert "voluntary" in result.meta.disclaimer.lower()
