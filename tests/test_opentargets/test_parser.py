"""Testes para opentargets/parser.py."""

from __future__ import annotations

import json
from pathlib import Path

from hypokrates.opentargets.parser import (
    parse_adverse_events,
    parse_adverse_events_meta,
    parse_search_drug,
)

GOLDEN = Path(__file__).parent.parent / "golden_data" / "opentargets"


class TestParseSearchDrug:
    """Testes para parse_search_drug()."""

    def test_found(self) -> None:
        data = json.loads((GOLDEN / "search_propofol.json").read_text())["data"]
        result = parse_search_drug(data)
        assert result == "CHEMBL526"

    def test_empty_hits(self) -> None:
        result = parse_search_drug({"search": {"hits": []}})
        assert result is None

    def test_no_search_field(self) -> None:
        result = parse_search_drug({})
        assert result is None

    def test_null_search(self) -> None:
        result = parse_search_drug({"search": None})
        assert result is None


class TestParseAdverseEvents:
    """Testes para parse_adverse_events()."""

    def test_parses_events(self) -> None:
        data = json.loads((GOLDEN / "adverse_events_propofol.json").read_text())["data"]
        events = parse_adverse_events(data)
        assert len(events) == 5
        names = [e.name for e in events]
        assert "Cardiac arrest" in names
        assert "Bradycardia" in names

    def test_log_lr_values(self) -> None:
        data = json.loads((GOLDEN / "adverse_events_propofol.json").read_text())["data"]
        events = parse_adverse_events(data)
        pris = next(e for e in events if "infusion" in e.name.lower())
        assert pris.log_lr == 45.67

    def test_meddra_code(self) -> None:
        data = json.loads((GOLDEN / "adverse_events_propofol.json").read_text())["data"]
        events = parse_adverse_events(data)
        cardiac = next(e for e in events if e.name == "Cardiac arrest")
        assert cardiac.meddra_code == "10007515"

    def test_empty_drug(self) -> None:
        events = parse_adverse_events({})
        assert events == []

    def test_no_adverse_events(self) -> None:
        events = parse_adverse_events({"drug": {}})
        assert events == []

    def test_null_drug(self) -> None:
        events = parse_adverse_events({"drug": None})
        assert events == []


class TestParseAdverseEventsMeta:
    """Testes para parse_adverse_events_meta()."""

    def test_count_and_critical_value(self) -> None:
        data = json.loads((GOLDEN / "adverse_events_propofol.json").read_text())["data"]
        count, cv = parse_adverse_events_meta(data)
        assert count == 150
        assert cv == 3.84

    def test_empty_data(self) -> None:
        count, cv = parse_adverse_events_meta({})
        assert count == 0
        assert cv == 0.0
