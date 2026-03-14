"""Funções de cálculo — pura matemática, sem side effects."""

from __future__ import annotations

import math

from hypokrates.stats.constants import (
    SIGNIFICANCE_THRESHOLD_IC,
    SIGNIFICANCE_THRESHOLD_PRR,
    SIGNIFICANCE_THRESHOLD_ROR,
)
from hypokrates.stats.models import ContingencyTable, DisproportionalityResult

# Z para IC 95%
_Z_95: float = 1.96
_LN2: float = math.log(2)
_LN2_SQ: float = _LN2**2


def compute_prr(table: ContingencyTable) -> DisproportionalityResult:
    """PRR = (a/(a+b)) / (c/(c+d)), CI via Rothman-Greenland.

    Fórmula:
        PRR = [a/(a+b)] / [c/(c+d)]
        ln(PRR) ± 1.96 * sqrt(1/a - 1/(a+b) + 1/c - 1/(c+d))

    Se alguma célula impossibilita o cálculo (divisão por zero),
    retorna valor=0 com CI=[0, 0] e significant=False.
    """
    a, b, c, d = table.a, table.b, table.c, table.d
    ab = a + b
    cd = c + d

    if a == 0 or ab == 0 or c == 0 or cd == 0:
        return DisproportionalityResult(
            measure="PRR",
            value=0.0,
            ci_lower=0.0,
            ci_upper=0.0,
            significant=False,
        )

    prr = (a / ab) / (c / cd)
    ln_prr = math.log(prr)
    se = math.sqrt(1 / a - 1 / ab + 1 / c - 1 / cd)
    ci_lower = math.exp(ln_prr - _Z_95 * se)
    ci_upper = math.exp(ln_prr + _Z_95 * se)

    return DisproportionalityResult(
        measure="PRR",
        value=prr,
        ci_lower=ci_lower,
        ci_upper=ci_upper,
        significant=ci_lower > SIGNIFICANCE_THRESHOLD_PRR,
    )


def compute_ror(table: ContingencyTable) -> DisproportionalityResult:
    """ROR = (a*d) / (b*c), CI via Woolf's method.

    Fórmula:
        ROR = (a*d) / (b*c)
        ln(ROR) ± 1.96 * sqrt(1/a + 1/b + 1/c + 1/d)

    Se alguma célula é zero, retorna valor=0 com CI=[0, 0].
    """
    a, b, c, d = table.a, table.b, table.c, table.d

    if a == 0 or b == 0 or c == 0 or d == 0:
        return DisproportionalityResult(
            measure="ROR",
            value=0.0,
            ci_lower=0.0,
            ci_upper=0.0,
            significant=False,
        )

    ror = (a * d) / (b * c)
    ln_ror = math.log(ror)
    se = math.sqrt(1 / a + 1 / b + 1 / c + 1 / d)
    ci_lower = math.exp(ln_ror - _Z_95 * se)
    ci_upper = math.exp(ln_ror + _Z_95 * se)

    return DisproportionalityResult(
        measure="ROR",
        value=ror,
        ci_lower=ci_lower,
        ci_upper=ci_upper,
        significant=ci_lower > SIGNIFICANCE_THRESHOLD_ROR,
    )


def compute_ic(table: ContingencyTable) -> DisproportionalityResult:
    """IC simplified — log2(observed/expected) com CI via aproximação normal.

    Esta é a versão simplificada do Information Component.
    NÃO é o BCPNN completo (Bate et al. 2002) que usa priors Beta.
    TODO: Implementar BCPNN com priors em sprint futuro.

    Fórmula:
        IC = log2(a * N / ((a+b) * (a+c)))
        Variância: V = 1 / (a * ln(2)^2)
        IC025 = IC - 1.96 * sqrt(V)
    """
    a = table.a
    n = table.n
    ab = a + table.b
    ac = a + table.c

    if a == 0 or n == 0 or ab == 0 or ac == 0:
        return DisproportionalityResult(
            measure="IC",
            value=0.0,
            ci_lower=0.0,
            ci_upper=0.0,
            significant=False,
        )

    expected = (ab * ac) / n
    ic = math.log2(a / expected)
    variance = 1 / (a * _LN2_SQ)
    se = math.sqrt(variance)
    ci_lower = ic - _Z_95 * se
    ci_upper = ic + _Z_95 * se

    return DisproportionalityResult(
        measure="IC",
        value=ic,
        ci_lower=ci_lower,
        ci_upper=ci_upper,
        significant=ci_lower > SIGNIFICANCE_THRESHOLD_IC,
    )


def build_table(
    drug_event: int,
    drug_total: int,
    event_total: int,
    n_total: int,
) -> ContingencyTable:
    """Constrói tabela 2x2 a partir de contagens marginais.

    Args:
        drug_event: Reports com droga E evento (a).
        drug_total: Total de reports com a droga (a + b).
        event_total: Total de reports com o evento (a + c).
        n_total: Total geral de reports (N).

    Se d resultar negativo (dados inconsistentes), clamp para 0.
    """
    a = drug_event
    b = drug_total - a
    c = event_total - a
    d = n_total - a - b - c
    return ContingencyTable(a=a, b=max(b, 0), c=max(c, 0), d=max(d, 0))
