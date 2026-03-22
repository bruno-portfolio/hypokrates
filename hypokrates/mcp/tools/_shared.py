"""Helpers compartilhados entre MCP tools."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from hypokrates.cross.models import StratumSignal


def format_measure(name: str, m: object) -> str:
    """Formata uma medida de desproporcionalidade (PRR/ROR/IC/EBGM)."""
    val = getattr(m, "value", 0.0)
    lo = getattr(m, "ci_lower", 0.0)
    hi = getattr(m, "ci_upper", 0.0)
    sig = "*" if getattr(m, "significant", False) else ""
    return f"- {name}: {val:.2f} (95% CI: {lo:.2f}-{hi:.2f}) {sig}"


def format_strata_table(
    title: str,
    col_name: str,
    strata: list[StratumSignal],
) -> list[str]:
    """Formata tabela markdown de strata (sex, age, country)."""
    items = [s for s in strata if not s.insufficient_data]
    if not items:
        return []
    lines = [
        "",
        f"## {title}",
        f"| Source | {col_name} | Reports | PRR | ROR | Signal |",
        "|--------|-----|---------|-----|-----|--------|",
    ]
    for s in items:
        sig_str = "YES" if s.signal_detected else "NO"
        lines.append(
            f"| {s.source} | {s.stratum_value} | {s.drug_event_count} | "
            f"{s.prr:.2f} | {s.ror:.2f} | {sig_str} |"
        )
    return lines
