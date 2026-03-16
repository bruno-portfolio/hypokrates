"""MCP tools para Canada Vigilance."""

from __future__ import annotations

from typing import TYPE_CHECKING

from hypokrates.canada import api as canada_api
from hypokrates.exceptions import HypokratesError

if TYPE_CHECKING:
    from mcp.server.fastmcp import FastMCP


def register(mcp: FastMCP) -> None:
    """Registra tools de Canada Vigilance no MCP server."""

    @mcp.tool()
    async def canada_signal(drug: str, event: str, suspect_only: bool = False) -> str:
        """Calculate PRR signal for a drug-event pair in Canada Vigilance database.

        Canada Vigilance contains ~738K adverse reaction reports from 1965 to present.
        Cross-country validation with FAERS increases confidence in detected signals.

        Requires Canada Vigilance bulk data configured via
        configure(canada_bulk_path='/path/to/extracted/').

        Args:
            drug: Active ingredient name (e.g., "propofol").
            event: MedDRA PT term (e.g., "Anaphylactic shock").
            suspect_only: Only count reports where drug role is Suspect.
        """
        try:
            result = await canada_api.canada_signal(drug, event, suspect_only=suspect_only)
        except HypokratesError as exc:
            return (
                f"Canada Vigilance not available: {exc}. "
                "Configure with configure(canada_bulk_path='/path/to/extracted/')."
            )
        except Exception as exc:
            return f"Canada Vigilance error: {exc}"

        signal_str = "YES" if result.signal_detected else "NO"
        return (
            f"# Canada Vigilance: {drug.upper()} + {event.upper()}\n"
            f"**Signal detected:** {signal_str}\n"
            f"**PRR:** {result.prr:.2f}\n"
            f"**Drug+Event reports:** {result.drug_event_count}\n"
            f"**Drug total:** {result.drug_total}\n"
            f"**Event total:** {result.event_total}\n"
            f"**Total reports in DB:** {result.total_reports}\n"
            f"\n---\n"
            f"**Note:** Canada Vigilance is a voluntary reporting system. "
            f"PRR measures disproportionality, not absolute risk."
        )

    @mcp.tool()
    async def canada_top_events(drug: str, limit: int = 10, suspect_only: bool = False) -> str:
        """Get top adverse events for a drug in Canada Vigilance database.

        Args:
            drug: Active ingredient name (e.g., "propofol").
            limit: Maximum events to return (default 10).
            suspect_only: Only count reports where drug role is Suspect.
        """
        try:
            events = await canada_api.canada_top_events(
                drug, limit=limit, suspect_only=suspect_only
            )
        except HypokratesError as exc:
            return (
                f"Canada Vigilance not available: {exc}. "
                "Configure with configure(canada_bulk_path='/path/to/extracted/')."
            )
        except Exception as exc:
            return f"Canada Vigilance error: {exc}"

        if not events:
            return f"No adverse events found for '{drug}' in Canada Vigilance."

        lines = [
            f"# Canada Vigilance Top Events: {drug.upper()}",
            f"**Total events shown:** {len(events)}",
            "",
            "| Rank | Event | Reports |",
            "|------|-------|---------|",
        ]

        for i, (ev, count) in enumerate(events, 1):
            lines.append(f"| {i} | {ev} | {count} |")

        return "\n".join(lines)

    @mcp.tool()
    async def canada_bulk_status() -> str:
        """Get status of the Canada Vigilance bulk data store."""
        try:
            status = await canada_api.canada_bulk_status()
        except HypokratesError as exc:
            return (
                f"Canada Vigilance not available: {exc}. "
                "Configure with configure(canada_bulk_path='/path/to/extracted/')."
            )
        except Exception as exc:
            return f"Canada Vigilance error: {exc}"

        return (
            f"# Canada Vigilance Store Status\n"
            f"**Loaded:** {'YES' if status.loaded else 'NO'}\n"
            f"**Total reports:** {status.total_reports:,}\n"
            f"**Total drug records:** {status.total_drugs:,}\n"
            f"**Total reaction records:** {status.total_reactions:,}\n"
            f"**Date range:** {status.date_range}"
        )
