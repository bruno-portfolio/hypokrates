"""Testes para hypokrates.faers.api — API pública, filtros, cache, erros."""

from __future__ import annotations

from typing import Any

import httpx
import respx

from hypokrates.config import configure
from hypokrates.faers.api import (
    _build_event_search,
    _build_search,
    adverse_events,
    compare,
    drugs_by_event,
    top_events,
)
from tests.helpers import assert_meta_complete


class TestBuildSearch:
    """Construção de queries OpenFDA."""

    def test_basic_drug_search(self) -> None:
        s = _build_search("propofol")
        assert 'patient.drug.openfda.generic_name.exact:"PROPOFOL"' in s

    def test_drug_name_uppercased(self) -> None:
        s = _build_search("propofol")
        assert "PROPOFOL" in s
        assert "propofol" not in s

    def test_with_age_min(self) -> None:
        s = _build_search("propofol", age_min=65)
        assert "patient.patientonsetage:[65 TO 999]" in s

    def test_with_age_max(self) -> None:
        s = _build_search("propofol", age_max=80)
        assert "patient.patientonsetage:[0 TO 80]" in s

    def test_with_age_range(self) -> None:
        s = _build_search("propofol", age_min=18, age_max=65)
        assert "patient.patientonsetage:[18 TO 65]" in s

    def test_with_sex_male(self) -> None:
        s = _build_search("propofol", sex="M")
        assert "patient.patientsex:1" in s

    def test_with_sex_female(self) -> None:
        s = _build_search("propofol", sex="F")
        assert "patient.patientsex:2" in s

    def test_with_serious_true(self) -> None:
        s = _build_search("propofol", serious=True)
        assert "serious:1" in s

    def test_with_serious_false(self) -> None:
        s = _build_search("propofol", serious=False)
        assert "serious:2" in s

    def test_combined_filters(self) -> None:
        s = _build_search("propofol", age_min=18, age_max=65, sex="M", serious=True)
        assert "PROPOFOL" in s
        assert "patient.patientonsetage:[18 TO 65]" in s
        assert "patient.patientsex:1" in s
        assert "serious:1" in s
        assert " AND " in s

    def test_no_filters_no_and(self) -> None:
        s = _build_search("propofol")
        assert " AND " not in s


class TestAdverseEvents:
    """API pública: adverse_events."""

    @respx.mock
    async def test_returns_faers_result(self, golden_faers_adverse_events: dict[str, Any]) -> None:
        configure(cache_enabled=False)
        respx.get(url__startswith="https://api.fda.gov/drug/event.json").mock(
            return_value=httpx.Response(200, json=golden_faers_adverse_events)
        )
        result = await adverse_events("propofol", use_cache=False)
        assert len(result.reports) == 3
        assert result.meta.source == "OpenFDA/FAERS"
        assert result.meta.total_results == 45230

    @respx.mock
    async def test_meta_complete(self, golden_faers_adverse_events: dict[str, Any]) -> None:
        configure(cache_enabled=False)
        respx.get(url__startswith="https://api.fda.gov/drug/event.json").mock(
            return_value=httpx.Response(200, json=golden_faers_adverse_events)
        )
        result = await adverse_events("propofol", use_cache=False)
        assert_meta_complete(result.meta)
        assert result.meta.query["drug"] == "propofol"

    @respx.mock
    async def test_returns_empty_for_unknown_drug(
        self, golden_faers_no_results: dict[str, Any]
    ) -> None:
        configure(cache_enabled=False)
        respx.get(url__startswith="https://api.fda.gov/drug/event.json").mock(
            return_value=httpx.Response(200, json=golden_faers_no_results)
        )
        result = await adverse_events("xyznotexist123", use_cache=False)
        assert len(result.reports) == 0

    @respx.mock
    async def test_passes_filters_to_query(
        self, golden_faers_adverse_events: dict[str, Any]
    ) -> None:
        configure(cache_enabled=False)
        respx.get(url__startswith="https://api.fda.gov/drug/event.json").mock(
            return_value=httpx.Response(200, json=golden_faers_adverse_events)
        )
        result = await adverse_events(
            "propofol", age_min=18, sex="M", serious=True, use_cache=False
        )
        assert result.meta.query["age_min"] == 18
        assert result.meta.query["sex"] == "M"
        assert result.meta.query["serious"] is True


class TestTopEvents:
    """API pública: top_events."""

    @respx.mock
    async def test_returns_top_events(self, golden_faers_top_events: dict[str, Any]) -> None:
        configure(cache_enabled=False)
        respx.get(url__startswith="https://api.fda.gov/drug/event.json").mock(
            return_value=httpx.Response(200, json=golden_faers_top_events)
        )
        result = await top_events("propofol", limit=10, use_cache=False)
        assert len(result.events) == 10
        assert result.events[0].term == "DEATH"
        assert result.events[0].count == 5234

    @respx.mock
    async def test_meta_has_query_info(self, golden_faers_top_events: dict[str, Any]) -> None:
        configure(cache_enabled=False)
        respx.get(url__startswith="https://api.fda.gov/drug/event.json").mock(
            return_value=httpx.Response(200, json=golden_faers_top_events)
        )
        result = await top_events("propofol", limit=10, use_cache=False)
        assert result.meta.query["drug"] == "propofol"
        assert result.meta.query["count"] == "reaction"


class TestBuildEventSearch:
    """Construcao de queries reverse lookup (evento -> drogas)."""

    def test_basic_event_search(self) -> None:
        s = _build_event_search("ANAPHYLACTIC SHOCK")
        assert 'patient.reaction.reactionmeddrapt.exact:"ANAPHYLACTIC SHOCK"' in s

    def test_uppercases_event(self) -> None:
        s = _build_event_search("hypotension")
        assert "HYPOTENSION" in s

    def test_with_suspect_only(self) -> None:
        s = _build_event_search("HYPOTENSION", suspect_only=True)
        assert "patient.drug.drugcharacterization:1" in s
        assert " AND " in s

    def test_no_suspect_no_and(self) -> None:
        s = _build_event_search("HYPOTENSION")
        assert " AND " not in s


class TestDrugsByEvent:
    """API publica: drugs_by_event (reverse lookup)."""

    @respx.mock
    async def test_returns_drugs(self, golden_faers_drugs_by_event: dict[str, Any]) -> None:
        configure(cache_enabled=False)
        respx.get(url__startswith="https://api.fda.gov/drug/event.json").mock(
            return_value=httpx.Response(200, json=golden_faers_drugs_by_event)
        )
        result = await drugs_by_event(
            "anaphylactic shock", limit=10, suspect_only=False, use_cache=False
        )
        assert len(result.drugs) == 10
        assert result.drugs[0].name == "PROPOFOL"
        assert result.drugs[0].count == 1969

    @respx.mock
    async def test_uppercases_event(self, golden_faers_drugs_by_event: dict[str, Any]) -> None:
        configure(cache_enabled=False)
        respx.get(url__startswith="https://api.fda.gov/drug/event.json").mock(
            return_value=httpx.Response(200, json=golden_faers_drugs_by_event)
        )
        result = await drugs_by_event("anaphylactic shock", suspect_only=False, use_cache=False)
        assert result.event == "ANAPHYLACTIC SHOCK"

    @respx.mock
    async def test_meta_has_query_info(self, golden_faers_drugs_by_event: dict[str, Any]) -> None:
        configure(cache_enabled=False)
        respx.get(url__startswith="https://api.fda.gov/drug/event.json").mock(
            return_value=httpx.Response(200, json=golden_faers_drugs_by_event)
        )
        result = await drugs_by_event(
            "anaphylactic shock", limit=10, suspect_only=False, use_cache=False
        )
        assert result.meta.query["event"] == "anaphylactic shock"
        assert result.meta.query["count"] == "drug"
        assert result.meta.source == "OpenFDA/FAERS"

    @respx.mock
    async def test_empty_for_unknown_event(self, golden_faers_no_results: dict[str, Any]) -> None:
        configure(cache_enabled=False)
        respx.get(url__startswith="https://api.fda.gov/drug/event.json").mock(
            return_value=httpx.Response(200, json=golden_faers_no_results)
        )
        result = await drugs_by_event("XYZNOTEXIST", suspect_only=False, use_cache=False)
        assert len(result.drugs) == 0

    @respx.mock
    async def test_default_suspect_only(self, golden_faers_drugs_by_event: dict[str, Any]) -> None:
        configure(cache_enabled=False)
        respx.get(url__startswith="https://api.fda.gov/drug/event.json").mock(
            return_value=httpx.Response(200, json=golden_faers_drugs_by_event)
        )
        result = await drugs_by_event("anaphylactic shock", use_cache=False)
        assert result.meta.query["suspect_only"] is True

    @respx.mock
    async def test_enriches_total_drug_reports(
        self, golden_faers_drugs_by_event: dict[str, Any]
    ) -> None:
        configure(cache_enabled=False)
        respx.get(url__startswith="https://api.fda.gov/drug/event.json").mock(
            return_value=httpx.Response(200, json=golden_faers_drugs_by_event)
        )
        result = await drugs_by_event("anaphylactic shock", use_cache=False)
        # All drugs should have total_drug_reports populated
        for d in result.drugs:
            assert d.total_drug_reports is not None


class TestCompare:
    """API pública: compare."""

    @respx.mock
    async def test_compare_returns_dict(self, golden_faers_top_events: dict[str, Any]) -> None:
        configure(cache_enabled=False)
        respx.get(url__startswith="https://api.fda.gov/drug/event.json").mock(
            return_value=httpx.Response(200, json=golden_faers_top_events)
        )
        results = await compare(["propofol", "ketamine"], use_cache=False)
        assert "propofol" in results
        assert "ketamine" in results

    @respx.mock
    async def test_compare_each_drug_has_events(
        self, golden_faers_top_events: dict[str, Any]
    ) -> None:
        configure(cache_enabled=False)
        respx.get(url__startswith="https://api.fda.gov/drug/event.json").mock(
            return_value=httpx.Response(200, json=golden_faers_top_events)
        )
        results = await compare(["propofol", "ketamine"], use_cache=False)
        for _drug, result in results.items():
            assert len(result.events) > 0
            assert result.meta.source == "OpenFDA/FAERS"

    @respx.mock
    async def test_compare_with_outcome_filter(
        self, golden_faers_adverse_events: dict[str, Any]
    ) -> None:
        configure(cache_enabled=False)
        respx.get(url__startswith="https://api.fda.gov/drug/event.json").mock(
            return_value=httpx.Response(200, json=golden_faers_adverse_events)
        )
        results = await compare(["propofol"], outcome="HYPOTENSION", use_cache=False)
        assert "propofol" in results
        assert results["propofol"].meta.query["outcome"] == "HYPOTENSION"
