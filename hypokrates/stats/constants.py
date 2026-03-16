"""Constantes para detecção de sinais."""

from __future__ import annotations

SIGNIFICANCE_THRESHOLD_PRR: float = 1.0  # ci_lower > 1.0
SIGNIFICANCE_THRESHOLD_ROR: float = 1.0  # ci_lower > 1.0
SIGNIFICANCE_THRESHOLD_IC: float = 0.0  # IC025 > 0
SIGNIFICANCE_THRESHOLD_EBGM: float = 1.0  # EB05 > 1.0
MIN_REPORT_COUNT: int = 3  # Mínimo de reports para calcular
MIN_MEASURES_FOR_SIGNAL: int = 2  # >= 2 significantes = sinal (heurística)

# EBGM/GPS hyperparameters — mixture of two gammas (DuMouchel 1999)
# Defaults averaged from PhViD and openEBGM packages.
# TODO: estimate from FAERS Bulk full matrix when loaded.
EBGM_ALPHA1: float = 0.2
EBGM_BETA1: float = 0.1
EBGM_ALPHA2: float = 2.0
EBGM_BETA2: float = 4.0
EBGM_P: float = 1 / 3  # mixing weight for component 1

SPIKE_THRESHOLD_SIGMA: float = 2.0  # quarters > mean + N*std flagged as spikes

SIGNAL_DISCLAIMER = (
    "signal_detected is a screening heuristic (>=2/3 measures significant), "
    "not a clinical determination. Each agency uses different criteria "
    "(FDA: EBGM/GPS, EMA: PRR, Uppsala: IC). "
    "Evaluate individual measures (prr, ror, ic, ebgm) for clinical decisions. "
    "EBGM uses fixed hyperparameters (not calibrated to current FAERS); "
    "FDA uses EB05>=2.0 for regulatory action."
)
