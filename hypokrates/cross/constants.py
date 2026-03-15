"""Constantes do módulo cross — thresholds de classificação."""

from __future__ import annotations

# Thresholds default — configuráveis via parâmetros em hypothesis()
DEFAULT_NOVEL_MAX: int = 0  # <= novel_max papers = novel_hypothesis
DEFAULT_EMERGING_MAX: int = 5  # <= emerging_max papers = emerging_signal, acima = known

# compare_signals
DEFAULT_COMPARE_TOP_N: int = 10
DEFAULT_COMPARE_CONCURRENCY: int = 3  # 2 signals x 3 events = 24 FAERS calls in flight
COMPARE_RATIO_EQUAL_THRESHOLD: float = 0.1  # within 10% = equal
