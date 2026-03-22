"""Constantes do módulo cross — thresholds de classificação."""

from __future__ import annotations

# Thresholds default — configuráveis via parâmetros em hypothesis()
DEFAULT_NOVEL_MAX: int = 0  # <= novel_max papers = novel_hypothesis
DEFAULT_EMERGING_MAX: int = 5  # <= emerging_max papers = emerging_signal, acima = known

# compare_signals
DEFAULT_COMPARE_TOP_N: int = 10
DEFAULT_COMPARE_CONCURRENCY: int = 3  # 2 signals x 3 events = 24 FAERS calls in flight
COMPARE_RATIO_EQUAL_THRESHOLD: float = 0.1  # within 10% = equal

# coadmin_analysis — Layer 2
OVERLAP_THRESHOLD: float = 0.5  # fração de overlap para classificar co-admin artifact
CO_ADMIN_COMPARE_TOP_N: int = 5  # max co-drugs para rodar signal() comparativo
SPECIFICITY_RATIO_THRESHOLD: float = 2.0  # PRR ratio acima = drug-specific

# investigate() — thresholds demográficos
STRATUM_SEX_NOTABLE_RATIO: float = 1.5  # flag se PRR M/F difere > 1.5x
STRATUM_AGE_NOTABLE_RATIO: float = 2.0  # flag se age_group PRR > 2x average
