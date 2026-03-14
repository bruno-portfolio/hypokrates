"""DailyMed — bulas FDA (SPL) para verificação de eventos em label."""

from __future__ import annotations

from hypokrates.dailymed.api import check_label, label_events
from hypokrates.dailymed.models import LabelCheckResult, LabelEventsResult

__all__ = [
    "LabelCheckResult",
    "LabelEventsResult",
    "check_label",
    "label_events",
]
