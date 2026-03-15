"""Funções de cálculo — pura matemática, sem side effects."""

from __future__ import annotations

import math

from scipy.special import polygamma

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

# Prior Jeffreys — menos informativo que uniform, padrão UMC (Uppsala)
_BCPNN_ALPHA: float = 0.5


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
    """IC (BCPNN — Norén et al. 2006) com prior Jeffreys (alpha=0.5).

    Bayesian Confidence Propagation Neural Network. Usa priors Beta
    que fazem shrinkage de estimativas com poucos reports para o centro,
    resolvendo o problema de contagens pequenas.

    Formula:
        n* = N + 4*alpha
        IC = log2((a + alpha) * n* / ((a+b + 2*alpha) * (a+c + 2*alpha)))
        V = (1/ln2^2) * [psi1(a+alpha) + psi1(a+b+2*alpha) + psi1(a+c+2*alpha) - 3*psi1(n*)]
        IC025 = IC - 1.96 * sqrt(V)

    Referencia: Noren GN, Hopstadius J, Bate A (2006).
    Shrinkage observation-to-expected ratios for assessment of drug safety signals.
    Stat Methods Med Res. 15(6):565-77.
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

    alpha = _BCPNN_ALPHA
    n_star = n + 4 * alpha

    p11 = (a + alpha) / n_star
    p1_dot = (ab + 2 * alpha) / n_star
    p_dot1 = (ac + 2 * alpha) / n_star

    ic = math.log2(p11 / (p1_dot * p_dot1))

    # Variância via trigamma (polygamma de ordem 1)
    variance = (1 / _LN2_SQ) * float(
        polygamma(1, a + alpha)
        + polygamma(1, ab + 2 * alpha)
        + polygamma(1, ac + 2 * alpha)
        - 3 * polygamma(1, n_star)
    )
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
