"""MCP tools para FAERS."""

from __future__ import annotations

import json
from typing import TYPE_CHECKING

from hypokrates.faers import api as faers_api

if TYPE_CHECKING:
    from mcp.server.fastmcp import FastMCP


def register(mcp: FastMCP) -> None:
    """Registra tools FAERS no MCP server."""

    @mcp.tool()
    async def adverse_events(drug: str, limit: int = 10) -> str:
        """Search adverse events for a drug in FDA FAERS database.

        Args:
            drug: Generic drug name (e.g., "propofol").
            limit: Max reports to return.
        """
        result = await faers_api.adverse_events(drug, limit=limit)
        reports_summary = [
            {"id": r.safety_report_id, "reactions": [rx.term for rx in r.reactions]}
            for r in result.reports[:10]
        ]
        return json.dumps(
            {
                "drug": drug,
                "total": result.meta.total_results,
                "reports_shown": len(reports_summary),
                "reports": reports_summary,
            },
            indent=2,
        )

    @mcp.tool()
    async def top_events(drug: str, limit: int = 10) -> str:
        """Get top adverse events for a drug from FAERS.

        Args:
            drug: Generic drug name.
            limit: Number of top events.
        """
        result = await faers_api.top_events(drug, limit=limit)
        lines = [f"# Top Events: {drug.upper()}", ""]
        for ev in result.events:
            lines.append(f"- **{ev.term}**: {ev.count} reports")
        return "\n".join(lines)

    @mcp.tool()
    async def drugs_by_event(event: str, limit: int = 10) -> str:
        """Get top drugs reported for an adverse event from FAERS (reverse lookup).

        Useful for finding which drugs are most associated with a specific
        adverse event in the FDA spontaneous reporting database.

        Args:
            event: MedDRA adverse event term (e.g., "anaphylactic shock").
            limit: Number of top drugs to return.
        """
        result = await faers_api.drugs_by_event(event, limit=limit)
        if not result.drugs:
            return f"No drugs found for event '{event}' in FAERS."
        lines = [
            f"# Top Drugs for: {result.event}",
            f"**Total:** {len(result.drugs)} drugs",
            "",
        ]
        for i, d in enumerate(result.drugs, 1):
            lines.append(f"{i:2}. **{d.name}**: {d.count:,} reports")
        lines.append("")
        lines.append("---")
        lines.append("*Source: OpenFDA/FAERS — voluntary reporting, counts ≠ risk*")
        return "\n".join(lines)

    @mcp.tool()
    async def compare_drugs(drugs: str, limit: int = 10) -> str:
        """Compare adverse events between multiple drugs.

        Args:
            drugs: Comma-separated drug names (e.g., "propofol,etomidate").
            limit: Top N events per drug.
        """
        drug_list = [d.strip() for d in drugs.split(",")]
        results = await faers_api.compare(drug_list, limit=limit)
        lines = ["# Drug Comparison", ""]
        for drug_name, result in results.items():
            lines.append(f"## {drug_name.upper()}")
            for ev in result.events:
                lines.append(f"- {ev.term}: {ev.count}")
            lines.append("")
        return "\n".join(lines)
