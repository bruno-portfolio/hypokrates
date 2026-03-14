"""Detecção de sinais estatísticos — PRR, ROR, IC (simplified)."""

from hypokrates.stats.api import signal
from hypokrates.stats.models import ContingencyTable, DisproportionalityResult, SignalResult

__all__ = [
    "ContingencyTable",
    "DisproportionalityResult",
    "SignalResult",
    "signal",
]
