from __future__ import annotations

from typing import TYPE_CHECKING

from hypokrates.canada import api as canada_api
from hypokrates.exceptions import HypokratesError
from hypokrates.faers_bulk.models import StrataFilter
from hypokrates.mcp.tools._shared import format_measure
from hypokrates.stats.measures import compute_ebgm, compute_ic, compute_prr, compute_ror

if TYPE_CHECKING:
    from mcp.server.fastmcp import FastMCP

_UNAVAILABLE_MSG = (
    "Canada Vigilance not available: {}. "
    "Configure with configure(canada_bulk_path='/path/to/extracted/')."
)


def register(mcp: FastMCP) -> None:
    @mcp.tool()
    async def canada_signal(
        drug: str,
        event: str,
        suspect_only: bool = False,
        sex: str | None = None,
        age_group: str | None = None,
    ) -> str:
        """Calculate PRR signal for a drug-event pair in Canada Vigilance database.

        Canada Vigilance contains ~738K adverse reaction reports from 1965 to present.
        Cross-country validation with FAERS increases confidence in detected signals.

        Supports demographic stratification via sex and age_group parameters.

        Requires Canada Vigilance bulk data configured via
        configure(canada_bulk_path='/path/to/extracted/').

        Args:
            drug: Active ingredient name (e.g., "propofol").
            event: MedDRA PT term (e.g., "Anaphylactic shock").
            suspect_only: Only count reports where drug role is Suspect.
            sex: Filter by sex: "M" or "F" (optional).
            age_group: Filter by age group: "0-17", "18-44", "45-64", "65+" (optional).
        """
        strata = None
        if sex is not None or age_group is not None:
            strata = StrataFilter(sex=sex, age_group=age_group)

        try:
            result = await canada_api.canada_signal(
                drug, event, suspect_only=suspect_only, strata=strata
            )
        except HypokratesError as exc:
            return _UNAVAILABLE_MSG.format(exc)
        except Exception as exc:
            return f"Canada Vigilance error: {exc}"

        signal_str = "YES" if result.signal_detected else "NO"

        # Compute full measures with CIs for display
        measures_lines = ""
        if result.table is not None:
            prr_m = compute_prr(result.table)
            ror_m = compute_ror(result.table)
            ic_m = compute_ic(result.table)
            ebgm_m = compute_ebgm(result.table)
            measures_lines = (
                "\n## Disproportionality Measures\n"
                f"{format_measure('PRR', prr_m)}\n"
                f"{format_measure('ROR', ror_m)}\n"
                f"{format_measure('IC ', ic_m)}\n"
                f"{format_measure('EBGM', ebgm_m)}\n"
            )

        return (
            f"# Canada Vigilance: {drug.upper()} + {event.upper()}\n"
            f"**Signal detected:** {signal_str}\n"
            f"**Drug+Event reports:** {result.drug_event_count}\n"
            f"**Drug total:** {result.drug_total}\n"
            f"**Event total:** {result.event_total}\n"
            f"**Total reports in DB:** {result.total_reports}\n"
            f"{measures_lines}"
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
            return _UNAVAILABLE_MSG.format(exc)
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
            return _UNAVAILABLE_MSG.format(exc)
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
