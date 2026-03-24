from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING

from hypokrates.faers.client import FAERSClient
from hypokrates.mcp.tools._shared import format_measure as _format_measure
from hypokrates.stats import api as stats_api

if TYPE_CHECKING:
    from mcp.server.fastmcp import FastMCP


def register(mcp: FastMCP) -> None:
    @mcp.tool()
    async def signal(
        drug: str,
        event: str,
        suspect_only: bool = False,
        use_bulk: bool | None = None,
    ) -> str:
        """Detect disproportionality signal for a drug-event pair in FAERS.

        Computes PRR, ROR, and IC from the 2x2 contingency table.
        Auto-detects FAERS Bulk data (deduplicated by CASEID) when available.

        Args:
            drug: Generic drug name.
            event: Adverse event term.
            suspect_only: Only count reports where drug is suspect (not concomitant).
            use_bulk: None=auto-detect, true=force bulk, false=force API.
        """
        result = await stats_api.signal(drug, event, suspect_only=suspect_only, use_bulk=use_bulk)
        if result.no_data:
            detected = "NO DATA"
        elif result.signal_detected:
            detected = "YES"
        else:
            detected = "NO"
        lines = [
            f"# Signal Detection: {drug.upper()} + {event.upper()}",
            f"**Signal detected:** {detected}",
            f"**Source:** {result.meta.source}",
        ]
        if result.no_data:
            lines.append("**⚠ No FAERS reports found for this drug-event term.**")
        lines += [
            "",
            "## Measures",
            _format_measure("PRR", result.prr),
            _format_measure("ROR", result.ror),
            _format_measure("IC ", result.ic),
            _format_measure("EBGM", result.ebgm),
            "",
            "## Contingency Table",
            f"- drug+event: {result.table.a}",
            f"- drug+!event: {result.table.b}",
            f"- !drug+event: {result.table.c}",
            f"- !drug+!event: {result.table.d}",
        ]
        return "\n".join(lines)

    @mcp.tool()
    async def batch_signal(
        pairs: list[dict[str, str]],
        suspect_only: bool = False,
    ) -> str:
        """Detect disproportionality signals for MULTIPLE drug-event pairs in one call.

        Much faster than calling signal() multiple times — shares HTTP client,
        rate limiter, and fetches drug_total/n_total only once per drug.

        Use this whenever you need to check 2+ drug-event pairs.

        Args:
            pairs: List of {"drug": "...", "event": "..."} dicts.
            suspect_only: Only count reports where drug is suspect (not concomitant).
        """
        if not pairs:
            return "No pairs provided."

        client = FAERSClient()
        try:
            tasks = [
                stats_api.signal(
                    p["drug"],
                    p["event"],
                    suspect_only=suspect_only,
                    _client=client,
                )
                for p in pairs
            ]
            results = await asyncio.gather(*tasks, return_exceptions=True)
        finally:
            await client.close()

        sections: list[str] = []
        for pair, result in zip(pairs, results, strict=True):
            drug = pair["drug"].upper()
            event = pair["event"].upper()
            if isinstance(result, BaseException):
                sections.append(f"## {drug} + {event}\n**Error:** {result}")
                continue
            detected = "YES" if result.signal_detected else "NO"
            sections.append(
                f"## {drug} + {event}\n"
                f"**Signal:** {detected} | "
                f"PRR={getattr(result.prr, 'value', 0):.2f} "
                f"({getattr(result.prr, 'ci_lower', 0):.2f}-"
                f"{getattr(result.prr, 'ci_upper', 0):.2f})"
                f"{'*' if getattr(result.prr, 'significant', False) else ''} | "
                f"ROR={getattr(result.ror, 'value', 0):.2f} | "
                f"IC={getattr(result.ic, 'value', 0):.2f} | "
                f"EBGM={getattr(result.ebgm, 'value', 0):.2f} | "
                f"n={result.table.a}"
            )

        header = f"# Batch Signal Detection ({len(pairs)} pairs)"
        return "\n\n".join([header, *sections])

    @mcp.tool()
    async def signal_timeline(
        drug: str,
        event: str,
        suspect_only: bool = False,
    ) -> str:
        """Build quarterly time series of FAERS reports for a drug-event pair.

        Detects stimulated reporting, litigation spikes, and temporal patterns.
        Quarters with count > mean + 2*std are flagged as spikes.

        Args:
            drug: Generic drug name (e.g., "propofol").
            event: Adverse event term (e.g., "anhedonia").
            suspect_only: Only count reports where drug is suspect (not concomitant).
        """
        result = await stats_api.signal_timeline(drug, event, suspect_only=suspect_only)
        lines = [
            f"# Timeline: {drug.upper()} + {event.upper()}",
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
