"""MCP tools para ClinicalTrials.gov."""

from __future__ import annotations

from typing import TYPE_CHECKING

from hypokrates.trials import api as trials_api

if TYPE_CHECKING:
    from mcp.server.fastmcp import FastMCP


def register(mcp: FastMCP) -> None:
    """Registra tools de ClinicalTrials.gov no MCP server."""

    @mcp.tool()
    async def search_trials(drug: str, event: str) -> str:
        """Search ClinicalTrials.gov for trials related to a drug-event pair.

        Returns matching clinical trials with their status and phase.

        Args:
            drug: Generic drug name (e.g., "propofol").
            event: Adverse event or condition term (e.g., "hypotension").
        """
        result = await trials_api.search_trials(drug, event)

        lines: list[str] = [
            f"# Trials: {drug.upper()} + {event.upper()}",
            f"**Total trials:** {result.total_count}",
            f"**Active trials:** {result.active_count}",
        ]

        if result.trials:
            lines.append("")
            lines.append("## Studies")
            for trial in result.trials:
                status_str = f" [{trial.status}]" if trial.status else ""
                phase_str = f" ({trial.phase})" if trial.phase else ""
                lines.append(f"- **{trial.nct_id}**{status_str}{phase_str}: {trial.title}")
        else:
            lines.append("\nNo matching trials found.")

        return "\n".join(lines)
