"""MCP tools para signal detection."""

from __future__ import annotations

from typing import TYPE_CHECKING

from hypokrates.stats import api as stats_api

if TYPE_CHECKING:
    from mcp.server.fastmcp import FastMCP


def _format_measure(name: str, m: object) -> str:
    """Formata uma medida de desproporcionalidade."""
    val = getattr(m, "value", 0.0)
    lo = getattr(m, "ci_lower", 0.0)
    hi = getattr(m, "ci_upper", 0.0)
    sig = "*" if getattr(m, "significant", False) else ""
    return f"- {name}: {val:.2f} (95% CI: {lo:.2f}-{hi:.2f}) {sig}"


def register(mcp: FastMCP) -> None:
    """Registra tools de stats no MCP server."""

    @mcp.tool()
    async def signal(drug: str, event: str) -> str:
        """Detect disproportionality signal for a drug-event pair in FAERS.

        Computes PRR, ROR, and IC (simplified) from the 2x2 contingency table.

        Args:
            drug: Generic drug name.
            event: Adverse event term.
        """
        result = await stats_api.signal(drug, event)
        detected = "YES" if result.signal_detected else "NO"
        lines = [
            f"# Signal Detection: {drug.upper()} + {event.upper()}",
            f"**Signal detected:** {detected}",
            "",
            "## Measures",
            _format_measure("PRR", result.prr),
            _format_measure("ROR", result.ror),
            _format_measure("IC ", result.ic),
            "",
            "## Contingency Table",
            f"- drug+event: {result.table.a}",
            f"- drug+!event: {result.table.b}",
            f"- !drug+event: {result.table.c}",
            f"- !drug+!event: {result.table.d}",
        ]
        return "\n".join(lines)
