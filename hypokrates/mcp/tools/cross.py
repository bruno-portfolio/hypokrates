"""MCP tools para cross-reference de hipóteses."""

from __future__ import annotations

from typing import TYPE_CHECKING

from hypokrates.cross import api as cross_api

if TYPE_CHECKING:
    from mcp.server.fastmcp import FastMCP


def register(mcp: FastMCP) -> None:
    """Registra tools de cross-reference no MCP server."""

    @mcp.tool()
    async def hypothesis(drug: str, event: str) -> str:
        """Cross-reference FAERS signal with PubMed literature for a drug-event pair.

        Classifies the pair as novel_hypothesis, emerging_signal, known_association,
        or no_signal based on disproportionality analysis and literature count.

        Args:
            drug: Generic drug name.
            event: Adverse event term.
        """
        result = await cross_api.hypothesis(drug, event)
        lines = [
            f"# Hypothesis: {drug.upper()} + {event.upper()}",
            f"**Classification:** {result.classification.value}",
            f"**Signal detected:** {'YES' if result.signal.signal_detected else 'NO'}",
            f"**Literature count:** {result.literature_count}",
            "",
            "## Summary",
            result.summary,
        ]
        if result.articles:
            lines.append("")
            lines.append("## Articles")
            for art in result.articles:
                lines.append(f"- [{art.pmid}] {art.title}")
        return "\n".join(lines)
