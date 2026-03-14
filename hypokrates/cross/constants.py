"""Constantes do módulo cross — thresholds de classificação."""

from __future__ import annotations

# Thresholds default — configuráveis via parâmetros em hypothesis()
DEFAULT_NOVEL_MAX: int = 0  # <= novel_max papers = novel_hypothesis
DEFAULT_EMERGING_MAX: int = 5  # <= emerging_max papers = emerging_signal, acima = known
