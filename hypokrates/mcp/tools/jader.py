"""MCP tools para JADER (farmacovigilância japonesa)."""

from __future__ import annotations

from typing import TYPE_CHECKING

from hypokrates.exceptions import HypokratesError
from hypokrates.jader import api as jader_api
from hypokrates.jader.models import MappingConfidence
from hypokrates.mcp.tools._shared import format_measure
from hypokrates.stats.measures import compute_ebgm, compute_ic, compute_prr, compute_ror

if TYPE_CHECKING:
    from mcp.server.fastmcp import FastMCP


def register(mcp: FastMCP) -> None:
    """Registra tools de JADER no MCP server."""

    @mcp.tool()
    async def jader_signal(drug: str, event: str, suspect_only: bool = False) -> str:
        """Calculate PRR signal for a drug-event pair in JADER (Japanese) database.

        JADER contains ~970K adverse drug event reports from 2004 to present (PMDA).
        Drug/event names are translated from Japanese — check mapping confidence.

        Requires JADER bulk data configured via
        configure(jader_bulk_path='/path/to/jader/csvs/').

        Args:
            drug: Active ingredient name in English (e.g., "propofol").
            event: MedDRA PT term in English (e.g., "Anaphylactic shock").
            suspect_only: Only count reports where drug role is Suspect (被疑薬).
        """
        try:
            result = await jader_api.jader_signal(drug, event, suspect_only=suspect_only)
        except HypokratesError as exc:
            return (
                f"JADER not available: {exc}. "
                "Configure with configure(jader_bulk_path='/path/to/jader/csvs/')."
            )
        except Exception as exc:
            return f"JADER error: {exc}"

        signal_str = "YES" if result.signal_detected else "NO"

        confidence_warning = ""
        if (
            result.drug_confidence != MappingConfidence.EXACT
            or result.event_confidence != MappingConfidence.EXACT
        ):
            confidence_warning = (
                f"\n**⚠ Mapping confidence:** drug={result.drug_confidence.value}, "
                f"event={result.event_confidence.value}\n"
            )

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
            f"# JADER (Japan): {drug.upper()} + {event.upper()}\n"
            f"**Signal detected:** {signal_str}\n"
            f"**Drug+Event reports:** {result.drug_event_count}\n"
            f"**Drug total:** {result.drug_total}\n"
            f"**Event total:** {result.event_total}\n"
            f"**Total reports in DB:** {result.total_reports}\n"
            f"{confidence_warning}"
            f"{measures_lines}"
            f"\n---\n"
            f"**Note:** {result.meta.disclaimer}"
        )

    @mcp.tool()
    async def jader_top_events(drug: str, limit: int = 10, suspect_only: bool = False) -> str:
        """Get top adverse events for a drug in JADER (Japanese) database.

        Args:
            drug: Active ingredient name in English (e.g., "propofol").
            limit: Maximum events to return (default 10).
            suspect_only: Only count reports where drug role is Suspect (被疑薬).
        """
        try:
            events = await jader_api.jader_top_events(drug, limit=limit, suspect_only=suspect_only)
        except HypokratesError as exc:
            return (
                f"JADER not available: {exc}. "
                "Configure with configure(jader_bulk_path='/path/to/jader/csvs/')."
            )
        except Exception as exc:
            return f"JADER error: {exc}"

        if not events:
            return f"No adverse events found for '{drug}' in JADER."

        lines = [
            f"# JADER Top Events: {drug.upper()}",
            f"**Total events shown:** {len(events)}",
            "",
            "| Rank | Event | Reports |",
            "|------|-------|---------|",
        ]

        for i, (ev, count) in enumerate(events, 1):
            lines.append(f"| {i} | {ev} | {count} |")

        lines.append("\n---\n**Note:** JADER source — drug/event names translated from Japanese.")

        return "\n".join(lines)

    @mcp.tool()
    async def jader_bulk_status() -> str:
        """Get status of the JADER (Japanese) bulk data store."""
        try:
            status = await jader_api.jader_bulk_status()
        except HypokratesError as exc:
            return (
                f"JADER not available: {exc}. "
                "Configure with configure(jader_bulk_path='/path/to/jader/csvs/')."
            )
        except Exception as exc:
            return f"JADER error: {exc}"

        total_drugs_mapped = status.exact_drug_mappings + status.inferred_drug_mappings
        total_events_mapped = status.exact_event_mappings + status.inferred_event_mappings

        return (
            f"# JADER Store Status\n"
            f"**Loaded:** {'YES' if status.loaded else 'NO'}\n"
            f"**Total reports (deduplicated):** {status.total_reports:,}\n"
            f"**Total drug records:** {status.total_drugs:,}\n"
            f"**Total reaction records:** {status.total_reactions:,}\n"
            f"**Case ID range:** {status.date_range}\n"
            f"\n## JP→EN Mapping Coverage\n"
            f"**Drugs:** {total_drugs_mapped:,} mapped "
            f"({status.exact_drug_mappings:,} exact, "
            f"{status.inferred_drug_mappings:,} inferred), "
            f"{status.unmapped_drugs:,} unmapped\n"
            f"**Events:** {total_events_mapped:,} mapped "
            f"({status.exact_event_mappings:,} exact, "
            f"{status.inferred_event_mappings:,} inferred), "
            f"{status.unmapped_events:,} unmapped"
        )
