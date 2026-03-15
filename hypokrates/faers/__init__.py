"""FAERS module — OpenFDA adverse event data."""

from hypokrates.faers.api import adverse_events, compare, drugs_by_event, top_events

__all__ = ["adverse_events", "compare", "drugs_by_event", "top_events"]
