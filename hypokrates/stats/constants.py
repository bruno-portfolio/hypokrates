"""Constantes para detecção de sinais."""

from __future__ import annotations

SIGNIFICANCE_THRESHOLD_PRR: float = 1.0  # ci_lower > 1.0
SIGNIFICANCE_THRESHOLD_ROR: float = 1.0  # ci_lower > 1.0
SIGNIFICANCE_THRESHOLD_IC: float = 0.0  # IC025 > 0
MIN_REPORT_COUNT: int = 3  # Mínimo de reports para calcular
MIN_MEASURES_FOR_SIGNAL: int = 2  # >= 2 significantes = sinal (heurística)

SPIKE_THRESHOLD_SIGMA: float = 2.0  # quarters > mean + N*std flagged as spikes

SIGNAL_DISCLAIMER = (
    "signal_detected is a screening heuristic (>=2/3 measures significant), "
    "not a clinical determination. Each agency uses different criteria "
    "(FDA: EBGM/GPS, EMA: PRR, Uppsala: IC). "
    "Evaluate individual measures (prr, ror, ic) for clinical decisions."
)
