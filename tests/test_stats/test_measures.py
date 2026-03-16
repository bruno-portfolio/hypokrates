"""Testes para hypokrates.stats.measures — matemática pura."""

from __future__ import annotations

import json
import math
from pathlib import Path

import pytest

from hypokrates.stats.measures import (
    _BCPNN_ALPHA,
    build_table,
    compute_ebgm,
    compute_ic,
    compute_prr,
    compute_ror,
)
from hypokrates.stats.models import ContingencyTable

GOLDEN_DATA = Path(__file__).parents[1] / "golden_data" / "stats"


def _load_golden(name: str) -> dict[str, object]:
    path = GOLDEN_DATA / name
    return json.loads(path.read_text())  # type: ignore[no-any-return]


# ---------------------------------------------------------------------------
# Tabela padrão para testes (golden data)
# a=100, b=900, c=200, d=8800 → N=10000
# ---------------------------------------------------------------------------


@pytest.fixture()
def golden_table() -> ContingencyTable:
    data = _load_golden("signal_propofol_pris.json")
    t = data["table"]
    return ContingencyTable(a=t["a"], b=t["b"], c=t["c"], d=t["d"])  # type: ignore[arg-type]


class TestComputePRR:
    """Testes para compute_prr."""

    def test_known_values(self, golden_table: ContingencyTable) -> None:
        """a=100,b=900,c=200,d=8800 → PRR ≈ 4.5."""
        result = compute_prr(golden_table)
        assert result.measure == "PRR"
        assert math.isclose(result.value, 4.5, rel_tol=1e-6)

    def test_ci_contains_point_estimate(self, golden_table: ContingencyTable) -> None:
        result = compute_prr(golden_table)
        assert result.ci_lower < result.value < result.ci_upper

    def test_significant_when_ci_above_1(self, golden_table: ContingencyTable) -> None:
        result = compute_prr(golden_table)
        assert result.ci_lower > 1.0
        assert result.significant is True

    def test_not_significant_ci_below_1(self) -> None:
        """Tabela onde PRR ≈ 1.0 — não significante."""
        table = ContingencyTable(a=100, b=900, c=100, d=900)
        result = compute_prr(table)
        assert result.significant is False

    def test_zero_a_handled(self) -> None:
        table = ContingencyTable(a=0, b=1000, c=500, d=8500)
        result = compute_prr(table)
        assert result.value == 0.0
        assert result.significant is False

    def test_zero_c_handled(self) -> None:
        """c=0 → divisão por zero → retorna 0."""
        table = ContingencyTable(a=50, b=950, c=0, d=9000)
        result = compute_prr(table)
        assert result.value == 0.0
        assert result.significant is False


class TestComputeROR:
    """Testes para compute_ror."""

    def test_known_values(self, golden_table: ContingencyTable) -> None:
        """a=100,b=900,c=200,d=8800 → ROR = (100*8800)/(900*200) ≈ 4.889."""
        result = compute_ror(golden_table)
        assert result.measure == "ROR"
        expected_ror = (100 * 8800) / (900 * 200)
        assert math.isclose(result.value, expected_ror, rel_tol=1e-6)

    def test_ci_contains_point_estimate(self, golden_table: ContingencyTable) -> None:
        result = compute_ror(golden_table)
        assert result.ci_lower < result.value < result.ci_upper

    def test_significant(self, golden_table: ContingencyTable) -> None:
        result = compute_ror(golden_table)
        assert result.significant is True

    def test_zero_b_handled(self) -> None:
        table = ContingencyTable(a=100, b=0, c=200, d=9700)
        result = compute_ror(table)
        assert result.value == 0.0
        assert result.significant is False

    def test_zero_d_handled(self) -> None:
        table = ContingencyTable(a=100, b=400, c=500, d=0)
        result = compute_ror(table)
        assert result.value == 0.0
        assert result.significant is False

    def test_not_significant(self) -> None:
        """Tabela balanceada → ROR ≈ 1.0."""
        table = ContingencyTable(a=100, b=900, c=100, d=900)
        result = compute_ror(table)
        assert result.significant is False


class TestComputeIC:
    """Testa IC BCPNN (Norén et al. 2006) com prior Jeffreys."""

    def test_known_values(self, golden_table: ContingencyTable) -> None:
        """BCPNN IC = log2((a+alpha)*n* / ((a+b+2*alpha)*(a+c+2*alpha)))."""
        result = compute_ic(golden_table)
        assert result.measure == "IC"
        # Compute expected BCPNN IC inline
        alpha = 0.5
        n_star = 10000 + 4 * alpha
        p11 = (100 + alpha) / n_star
        p1_dot = (1000 + 2 * alpha) / n_star
        p_dot1 = (300 + 2 * alpha) / n_star
        expected_ic = math.log2(p11 / (p1_dot * p_dot1))
        assert math.isclose(result.value, expected_ic, rel_tol=1e-6)

    def test_ic025_positive_is_signal(self, golden_table: ContingencyTable) -> None:
        result = compute_ic(golden_table)
        assert result.ci_lower > 0
        assert result.significant is True

    def test_ic025_negative_no_signal(self) -> None:
        """Tabela balanceada → IC ≈ 0, IC025 < 0."""
        table = ContingencyTable(a=10, b=990, c=10, d=990)
        result = compute_ic(table)
        assert result.significant is False

    def test_zero_a_handled(self) -> None:
        table = ContingencyTable(a=0, b=1000, c=500, d=8500)
        result = compute_ic(table)
        assert result.value == 0.0
        assert result.significant is False

    def test_docstring_mentions_bcpnn(self) -> None:
        """Verifica que a docstring documenta BCPNN."""
        doc = compute_ic.__doc__ or ""
        assert "BCPNN" in doc

    def test_bcpnn_shrinkage_small_counts(self) -> None:
        """a=3 → BCPNN IC mais conservador (CI mais largo) que simple."""
        table = ContingencyTable(a=3, b=97, c=1, d=899)
        result = compute_ic(table)
        # Simple IC para comparação
        n = table.n
        ab = 3 + 97
        ac = 3 + 1
        simple_ic = math.log2(3 * n / (ab * ac))
        simple_se = math.sqrt(1 / (3 * math.log(2) ** 2))
        simple_ic025 = simple_ic - 1.96 * simple_se
        # BCPNN IC025 deve ser menor (mais conservador) que simple IC025
        assert result.ci_lower < simple_ic025
        # BCPNN IC value deve ser menor que simple (shrinkage)
        assert result.value < simple_ic

    def test_bcpnn_convergence_large_counts(self) -> None:
        """a=1000 → BCPNN ~= simple (prior é irrelevante em n grande)."""
        table = ContingencyTable(a=1000, b=9000, c=2000, d=88000)
        result = compute_ic(table)
        n = table.n
        simple_ic = math.log2(1000 * n / (10000 * 3000))
        assert math.isclose(result.value, simple_ic, rel_tol=0.01)

    def test_bcpnn_prior_effect(self) -> None:
        """a=1 → CI significativamente mais largo que simple (prior domina)."""
        table = ContingencyTable(a=1, b=99, c=2, d=898)
        result = compute_ic(table)
        simple_se = math.sqrt(1 / (1 * math.log(2) ** 2))
        simple_ci_width = 2 * 1.96 * simple_se
        bcpnn_ci_width = result.ci_upper - result.ci_lower
        # BCPNN CI deve ser mais largo que simple com a=1
        assert bcpnn_ci_width > simple_ci_width
        # E não deve ser significante com apenas 1 report
        assert result.significant is False

    def test_bcpnn_balanced_not_significant(self) -> None:
        """Tabela balanceada com a=10 → NOT significant."""
        table = ContingencyTable(a=10, b=990, c=10, d=990)
        result = compute_ic(table)
        assert result.significant is False
        assert result.ci_lower < 0

    def test_bcpnn_alpha_constant(self) -> None:
        """Verifica que _BCPNN_ALPHA é 0.5 (Jeffreys prior)."""
        assert _BCPNN_ALPHA == 0.5


class TestComputeEBGM:
    """Testa EBGM (GPS/DuMouchel 1999) — Empirical Bayes Geometric Mean."""

    def test_known_values(self, golden_table: ContingencyTable) -> None:
        """a=100,b=900,c=200,d=8800 → EBGM > 1.0 (sinal real)."""
        result = compute_ebgm(golden_table)
        assert result.measure == "EBGM"
        assert result.value > 1.0

    def test_ci_contains_point_estimate(self, golden_table: ContingencyTable) -> None:
        result = compute_ebgm(golden_table)
        assert result.ci_lower < result.value < result.ci_upper

    def test_significant_when_eb05_above_threshold(self, golden_table: ContingencyTable) -> None:
        result = compute_ebgm(golden_table)
        assert result.ci_lower > 1.0
        assert result.significant is True

    def test_not_significant_small_count(self) -> None:
        """a=1 → shrinkage → EB05 < 1.0."""
        table = ContingencyTable(a=1, b=999, c=200, d=8800)
        result = compute_ebgm(table)
        assert result.significant is False

    def test_zero_a_handled(self) -> None:
        table = ContingencyTable(a=0, b=1000, c=500, d=8500)
        result = compute_ebgm(table)
        assert result.value == 0.0
        assert result.significant is False

    def test_zero_e_handled(self) -> None:
        """E=0 (ab=0 ou ac=0) → retorna zeros."""
        table = ContingencyTable(a=0, b=0, c=500, d=8500)
        result = compute_ebgm(table)
        assert result.value == 0.0
        assert result.significant is False

    def test_shrinkage_small_counts(self) -> None:
        """a=3 → EBGM << N/E (shrinkage em ação)."""
        table = ContingencyTable(a=3, b=97, c=50, d=9850)
        result = compute_ebgm(table)
        # N/E sem shrinkage
        n = table.n
        e_val = (3 + 97) * (3 + 50) / n
        raw_ratio = 3 / e_val
        # EBGM deve ser menor que raw ratio (shrinkage)
        assert result.value < raw_ratio

    def test_convergence_large_counts(self) -> None:
        """a=1000 → EBGM ≈ N/E (prior é irrelevante)."""
        table = ContingencyTable(a=1000, b=9000, c=2000, d=88000)
        result = compute_ebgm(table)
        n = table.n
        e_val = (1000 + 9000) * (1000 + 2000) / n
        raw_ratio = 1000 / e_val
        assert math.isclose(result.value, raw_ratio, rel_tol=0.05)

    def test_eb05_below_ebgm(self, golden_table: ContingencyTable) -> None:
        """EB05 < EBGM sempre."""
        result = compute_ebgm(golden_table)
        assert result.ci_lower < result.value

    def test_deterministic_100x(self, golden_table: ContingencyTable) -> None:
        results = [compute_ebgm(golden_table).value for _ in range(100)]
        assert len(set(results)) == 1


class TestBuildTable:
    """Testes para build_table."""

    def test_from_marginals(self) -> None:
        table = build_table(drug_event=100, drug_total=1000, event_total=300, n_total=10000)
        assert table.a == 100
        assert table.b == 900
        assert table.c == 200
        assert table.d == 8800
        assert table.n == 10000

    def test_negative_d_clamped(self) -> None:
        """Se dados inconsistentes levam a d < 0, clamp para 0."""
        table = build_table(drug_event=100, drug_total=5000, event_total=6000, n_total=10000)
        assert table.d >= 0

    def test_negative_b_clamped(self) -> None:
        """Se drug_event > drug_total, b seria negativo — clamp."""
        table = build_table(drug_event=200, drug_total=100, event_total=300, n_total=10000)
        assert table.b >= 0

    def test_negative_c_clamped(self) -> None:
        """Se drug_event > event_total, c seria negativo — clamp."""
        table = build_table(drug_event=400, drug_total=1000, event_total=300, n_total=10000)
        assert table.c >= 0


class TestMeasuresDeterminism:
    """Testa determinismo das medidas."""

    def test_all_measures_deterministic_100x(self, golden_table: ContingencyTable) -> None:
        results_prr = [compute_prr(golden_table).value for _ in range(100)]
        results_ror = [compute_ror(golden_table).value for _ in range(100)]
        results_ic = [compute_ic(golden_table).value for _ in range(100)]
        results_ebgm = [compute_ebgm(golden_table).value for _ in range(100)]
        assert len(set(results_prr)) == 1
        assert len(set(results_ror)) == 1
        assert len(set(results_ic)) == 1
        assert len(set(results_ebgm)) == 1
