"""Helpers compartilhados entre MCP tools."""

from __future__ import annotations


def format_measure(name: str, m: object) -> str:
    """Formata uma medida de desproporcionalidade (PRR/ROR/IC/EBGM)."""
    val = getattr(m, "value", 0.0)
    lo = getattr(m, "ci_lower", 0.0)
    hi = getattr(m, "ci_upper", 0.0)
    sig = "*" if getattr(m, "significant", False) else ""
    return f"- {name}: {val:.2f} (95% CI: {lo:.2f}-{hi:.2f}) {sig}"
