"""Benchmark test runner — valida gold standards e controles negativos.

Roda contra FAERS API real. Usar: pytest -m benchmark
NAO roda por default (precisa de API calls).
"""

from __future__ import annotations

import pytest

from tests.benchmark.registry import (
    BENCHMARK_CASES,
    BenchmarkCategory,
    ExpectedDirection,
)


def _cases_by_category(category: BenchmarkCategory) -> list[object]:
    return [c for c in BENCHMARK_CASES if c.category == category]


@pytest.mark.benchmark
class TestGoldStandards:
    """Gold standards indiscutiveis DEVEM ser detectados."""

    @pytest.mark.parametrize(
        "case",
        _cases_by_category(BenchmarkCategory.KNOWN_SIGNAL),
        ids=lambda c: f"{c.drug}+{c.event}",
    )
    async def test_signal_detected(self, case: object) -> None:
        from hypokrates.stats.api import signal

        result = await signal(case.drug, case.event, suspect_only=True)  # type: ignore[union-attr]
        assert result.signal_detected, (
            f"FAIL gold standard: {case.drug}+{case.event}"  # type: ignore[union-attr]
        )


@pytest.mark.benchmark
class TestNegativeControls:
    """True negatives NAO devem ser detectados."""

    @pytest.mark.parametrize(
        "case",
        _cases_by_category(BenchmarkCategory.KNOWN_NOISE),
        ids=lambda c: f"{c.drug}+{c.event}",
    )
    async def test_no_signal(self, case: object) -> None:
        from hypokrates.stats.api import signal

        result = await signal(case.drug, case.event, suspect_only=True)  # type: ignore[union-attr]
        assert not result.signal_detected, (
            f"FAIL false positive: {case.drug}+{case.event}"  # type: ignore[union-attr]
        )


@pytest.mark.benchmark
class TestEmergingSmoke:
    """Emerging cases: smoke test — verifica que nao crasham."""

    @pytest.mark.parametrize(
        "case",
        _cases_by_category(BenchmarkCategory.EMERGING),
        ids=lambda c: f"{c.drug}+{c.event}",
    )
    async def test_runs_without_error(self, case: object) -> None:
        from hypokrates.stats.api import signal

        result = await signal(case.drug, case.event, suspect_only=True)  # type: ignore[union-attr]
        assert result.table.a >= 0


@pytest.mark.benchmark
class TestOntology:
    """MedDRA mapping: verifica que sinonimos sao tratados corretamente."""

    @pytest.mark.parametrize(
        "case",
        _cases_by_category(BenchmarkCategory.ONTOLOGY),
        ids=lambda c: f"{c.drug}+{c.event}",
    )
    async def test_ontology_signal(self, case: object) -> None:
        from hypokrates.stats.api import signal

        result = await signal(case.drug, case.event, suspect_only=True)  # type: ignore[union-attr]
        if case.expected_direction == ExpectedDirection.SIGNAL:  # type: ignore[union-attr]
            assert result.signal_detected, (
                f"FAIL ontology: {case.drug}+{case.event}"  # type: ignore[union-attr]
            )
