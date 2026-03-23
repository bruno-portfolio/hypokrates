from __future__ import annotations

import json
from typing import TYPE_CHECKING

from hypokrates.faers import api as faers_api

if TYPE_CHECKING:
    from mcp.server.fastmcp import FastMCP


def register(mcp: FastMCP) -> None:
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
    async def drugs_by_event(event: str, limit: int = 10, suspect_only: bool = True) -> str:
        """Get top drugs reported for an adverse event from FAERS (reverse lookup).

        Returns drugs ranked by report count with total drug reports for context.
        Default suspect_only=True reduces co-administration noise (e.g., propofol
        appearing in rocuronium anaphylaxis reports as concomitant).

        Args:
            event: MedDRA adverse event term (e.g., "anaphylactic shock").
            limit: Number of top drugs to return.
            suspect_only: Only count reports where drug is suspect (default True).
        """
        result = await faers_api.drugs_by_event(event, limit=limit, suspect_only=suspect_only)
        if not result.drugs:
            return f"No drugs found for event '{event}' in FAERS."
        role = "suspect only" if suspect_only else "all roles"
        lines = [
            f"# Top Drugs for: {result.event}",
            f"**Total:** {len(result.drugs)} drugs | **Role filter:** {role}",
            "",
            "| # | Drug | Event Reports | Drug Total | % |",
            "|---|------|--------------|------------|---|",
        ]
        for i, d in enumerate(result.drugs, 1):
            if d.total_drug_reports and d.total_drug_reports > 0:
                pct = d.count / d.total_drug_reports * 100
                lines.append(
                    f"| {i} | **{d.name}** | {d.count:,} | {d.total_drug_reports:,} | {pct:.1f}% |"
                )
            else:
                lines.append(f"| {i} | **{d.name}** | {d.count:,} | — | — |")
        lines.extend(
            [
                "",
                "---",
                "*Source: OpenFDA/FAERS — voluntary reporting. "
                "% = event reports / total drug reports (NOT incidence).*",
                "*Use `signal(drug, event)` for PRR disproportionality analysis.*",
            ]
        )
        return "\n".join(lines)

    @mcp.tool()
    async def co_suspect_profile(
        drug: str,
        event: str,
        sample_size: int = 100,
        suspect_only: bool = False,
    ) -> str:
        """Analyze co-suspect drug patterns for a drug+event pair in FAERS.

        Shows how many other drugs are listed as suspect in the same reports.
        High median suspects (>3) suggests co-administration confounding
        (e.g., OR setting where propofol, fentanyl, rocuronium all listed).

        Args:
            drug: Generic drug name (e.g., "propofol").
            event: Adverse event term (e.g., "anaphylactic shock").
            sample_size: Number of reports to analyze (max 100).
            suspect_only: Only count reports where drug is suspect.
        """
        clamped = min(sample_size, 100)
        result = await faers_api.co_suspect_profile(
            drug, event, sample_size=clamped, suspect_only=suspect_only
        )
        lines = [
            f"# Co-Suspect Profile: {drug.upper()} + {event.upper()}",
            f"**Sample size:** {result.sample_size} reports",
            f"**Median suspects/report:** {result.median_suspects:.1f}",
            f"**Mean suspects/report:** {result.mean_suspects:.1f}",
            f"**Max suspects in a report:** {result.max_suspects}",
            f"**Co-admin flag:** {'YES ⚠' if result.co_admin_flag else 'NO'}",
            "",
        ]
        if result.top_co_drugs:
            lines.append("## Top Co-Suspect Drugs")
            lines.append("")
            lines.append("| Drug | Reports |")
            lines.append("|------|---------|")
            for name, count in result.top_co_drugs:
                lines.append(f"| {name} | {count} |")
            lines.append("")
        if result.co_admin_flag:
            lines.extend(
                [
                    "---",
                    "**⚠ Co-administration detected.** High median suspect count suggests "
                    "this drug-event pair may be confounded by procedural co-administration. "
                    "PRR may be inflated by onipresence, not causality.",
                ]
            )
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
