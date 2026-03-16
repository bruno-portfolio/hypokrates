"""MCP tools para DailyMed (bulas FDA)."""

from __future__ import annotations

from typing import TYPE_CHECKING

from hypokrates.dailymed import api as dailymed_api

if TYPE_CHECKING:
    from mcp.server.fastmcp import FastMCP


def register(mcp: FastMCP) -> None:
    """Registra tools de DailyMed no MCP server."""

    @mcp.tool()
    async def label_events(drug: str) -> str:
        """Extract adverse reactions listed in a drug's FDA label (SPL) via DailyMed.

        Returns the list of adverse event terms found in the label's
        "Adverse Reactions" section.

        Args:
            drug: Generic drug name (e.g., "propofol").
        """
        result = await dailymed_api.label_events(drug)

        lines: list[str] = [f"# Label Events: {drug.upper()}"]

        if result.events:
            lines.append(f"**SET ID:** {result.set_id}")
            lines.append(f"**Events found:** {len(result.events)}")
            lines.append("")
            for event in result.events[:50]:  # limitar output
                lines.append(f"- {event}")
            if len(result.events) > 50:
                lines.append(f"... and {len(result.events) - 50} more")
        elif result.set_id:
            lines.append("No adverse reactions section found in label.")
        else:
            lines.append(
                "**⚠ No SPL found in DailyMed.** Drug may be withdrawn, "
                "not marketed in the US, or listed under a different name."
            )

        return "\n".join(lines)

    @mcp.tool()
    async def check_label(drug: str, event: str) -> str:
        """Check if a specific adverse event is listed in a drug's FDA label.

        Performs case-insensitive substring matching against the adverse reactions
        section of the drug's SPL label from DailyMed.

        Args:
            drug: Generic drug name (e.g., "propofol").
            event: Adverse event term (e.g., "bradycardia").
        """
        result = await dailymed_api.check_label(drug, event)

        lines: list[str] = [
            f"# Label Check: {drug.upper()} + {event.upper()}",
            f"**In label:** {'YES' if result.in_label else 'NO'}",
        ]
        if result.matched_terms:
            lines.append(f"**Matched terms:** {', '.join(result.matched_terms)}")
        if result.set_id:
            lines.append(f"**SET ID:** {result.set_id}")
        else:
            lines.append(
                "**⚠ No SPL found in DailyMed.** Drug may be withdrawn, "
                "not marketed in the US, or listed under a different name."
            )

        return "\n".join(lines)
