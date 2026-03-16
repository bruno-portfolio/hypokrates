"""MCP tools para FAERS Bulk (deduplicação por CASEID)."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from hypokrates.faers_bulk import api as bulk_api
from hypokrates.faers_bulk.constants import RoleCodFilter
from hypokrates.faers_bulk.timeline import bulk_signal_timeline
from hypokrates.mcp.tools._shared import format_measure as _format_measure

if TYPE_CHECKING:
    from mcp.server.fastmcp import FastMCP

logger = logging.getLogger(__name__)


def register(mcp: FastMCP) -> None:
    """Registra tools de FAERS Bulk no MCP server."""

    @mcp.tool()
    async def faers_bulk_status() -> str:
        """Show FAERS Bulk store status: loaded quarters, total cases, dedup stats.

        Use this to check if bulk data is available before running bulk queries.
        """
        try:
            status = await bulk_api.bulk_store_status()
        except Exception as exc:
            return f"FAERS Bulk store not available: {exc}"

        if not status.quarters_loaded:
            return (
                "# FAERS Bulk Store\n\n"
                "**Status:** Empty — no quarters loaded.\n\n"
                "Use `faers_bulk_load` to load FAERS quarterly ASCII ZIPs."
            )

        lines = [
            "# FAERS Bulk Store",
            f"**Total reports:** {status.total_reports:,}",
            f"**Deduplicated cases:** {status.deduped_cases:,}",
            f"**Quarters loaded:** {len(status.quarters_loaded)}",
            f"**Range:** {status.oldest_quarter} — {status.newest_quarter}",
            "",
            "## Quarters",
        ]
        for q in status.quarters_loaded:
            lines.append(
                f"- {q.quarter_key}: {q.demo_count:,} reports, "
                f"{q.drug_count:,} drug records, {q.reac_count:,} reactions"
            )

        return "\n".join(lines)

    @mcp.tool()
    async def faers_bulk_signal(
        drug: str,
        event: str,
        role_filter: str = "suspect",
    ) -> str:
        """Detect disproportionality signal using FAERS Bulk data (deduplicated by CASEID).

        Unlike the API-based signal, this uses locally stored quarterly ASCII files
        with proper CASEID deduplication. Supports PS-only analysis (impossible via API).

        Args:
            drug: Generic drug name (e.g., "propofol").
            event: Adverse event MedDRA term (e.g., "BRADYCARDIA").
            role_filter: Drug role filter: "suspect" (PS+SS), "ps_only" (PS only), "all".
        """
        available = await bulk_api.is_bulk_available()
        if not available:
            return (
                "FAERS Bulk store is empty. Load quarterly ASCII ZIPs first "
                "with `faers_bulk_load`."
            )

        try:
            rf = RoleCodFilter(role_filter)
        except ValueError:
            return f"Invalid role_filter: {role_filter}. Use: suspect, ps_only, all."

        result = await bulk_api.bulk_signal(drug, event, role_filter=rf)
        detected = "YES" if result.signal_detected else "NO"
        lines = [
            f"# Bulk Signal: {drug.upper()} + {event.upper()}",
            f"**Signal detected:** {detected}",
            f"**Source:** {result.meta.source}",
            f"**Role filter:** {role_filter}",
            "",
            "## Measures",
            _format_measure("PRR", result.prr),
            _format_measure("ROR", result.ror),
            _format_measure("IC ", result.ic),
            _format_measure("EBGM", result.ebgm),
            "",
            "## Contingency Table (deduplicated)",
            f"- drug+event: {result.table.a}",
            f"- drug+!event: {result.table.b}",
            f"- !drug+event: {result.table.c}",
            f"- !drug+!event: {result.table.d}",
        ]
        return "\n".join(lines)

    @mcp.tool()
    async def faers_bulk_load(zip_dir: str) -> str:
        """Load FAERS quarterly ASCII ZIPs from a directory into the bulk store.

        Scans the directory for files matching faers_ascii_*.zip and loads
        any quarters not already in the store. Idempotent — safe to re-run.

        NOTE: This may take several minutes for large datasets.

        Args:
            zip_dir: Directory path containing FAERS ASCII ZIP files.
        """
        from hypokrates.faers_bulk.loader import load_incremental

        try:
            total = await load_incremental(zip_dir)
        except Exception as exc:
            return f"Error loading FAERS data: {exc}"

        if total == 0:
            return "No new quarters to load (all already in store)."

        status = await bulk_api.bulk_store_status()
        return (
            f"Loaded {total:,} new demo rows.\n\n"
            f"**Total reports:** {status.total_reports:,}\n"
            f"**Deduplicated cases:** {status.deduped_cases:,}\n"
            f"**Quarters:** {len(status.quarters_loaded)}"
        )

    @mcp.tool()
    async def faers_bulk_timeline(
        drug: str,
        event: str,
        role_filter: str = "suspect",
    ) -> str:
        """Build quarterly timeline from FAERS Bulk data (deduplicated by CASEID).

        Shows report counts per quarter with spike detection.
        Requires bulk data to be loaded first.

        Args:
            drug: Generic drug name (e.g., "propofol").
            event: Adverse event MedDRA term (e.g., "BRADYCARDIA").
            role_filter: Drug role filter: "suspect" (PS+SS), "ps_only" (PS only), "all".
        """
        available = await bulk_api.is_bulk_available()
        if not available:
            return "FAERS Bulk store is empty. Load data first with `faers_bulk_load`."

        try:
            rf = RoleCodFilter(role_filter)
        except ValueError:
            return f"Invalid role_filter: {role_filter}. Use: suspect, ps_only, all."

        result = await bulk_signal_timeline(drug, event, role_filter=rf)

        lines = [
            f"# Bulk Timeline: {drug.upper()} + {event.upper()}",
            f"**Source:** {result.meta.source}",
            f"**Role filter:** {role_filter}",
            f"**Total reports:** {result.total_reports}",
            f"**Quarters:** {len(result.quarters)}",
            f"**Mean/quarter:** {result.mean_quarterly:.1f} (std: {result.std_quarterly:.1f})",
        ]
        if result.peak_quarter:
            lines.append(
                f"**Peak:** {result.peak_quarter.label} ({result.peak_quarter.count} reports)"
            )
        if result.spike_quarters:
            spike_labels = [f"{s.label} ({s.count})" for s in result.spike_quarters]
            lines.append(f"**Spikes detected:** {', '.join(spike_labels)}")
        else:
            lines.append("**Spikes detected:** none")

        lines.extend(["", "## Quarterly Counts", ""])
        spike_set = {(s.year, s.quarter) for s in result.spike_quarters}
        for q in result.quarters:
            spike_marker = " *** SPIKE" if (q.year, q.quarter) in spike_set else ""
            lines.append(f"  {q.label}: {q.count:>6}{spike_marker}")

        return "\n".join(lines)
