from __future__ import annotations

from typing import TYPE_CHECKING

from hypokrates.opentargets import api as opentargets_api

if TYPE_CHECKING:
    from mcp.server.fastmcp import FastMCP


def register(mcp: FastMCP) -> None:
    @mcp.tool()
    async def drug_adverse_events(drug: str) -> str:
        """Get adverse events for a drug from OpenTargets Platform with LRT scores.

        Uses FAERS-based log-likelihood ratio analysis from OpenTargets.
        No API key required.

        Args:
            drug: Generic drug name (e.g., "propofol").
        """
        result = await opentargets_api.drug_adverse_events(drug)

        if not result.chembl_id:
            return f"Drug '{drug}' not found in OpenTargets."

        lines = [
            f"# OpenTargets: {drug.upper()}",
            f"**ChEMBL ID:** {result.chembl_id}",
            f"**Total adverse events:** {result.total_count}",
            f"**Critical value:** {result.critical_value:.2f}",
            "",
        ]

        if result.adverse_events:
            lines.append("## Top Adverse Events (by LRT score)")
            lines.append("")
            # Sort by log_lr descending
            sorted_events = sorted(result.adverse_events, key=lambda x: x.log_lr, reverse=True)
            for ae in sorted_events[:20]:
                meddra = f" [{ae.meddra_code}]" if ae.meddra_code else ""
                lines.append(f"- **{ae.name}**{meddra} — logLR={ae.log_lr:.2f}, count={ae.count}")

            if len(result.adverse_events) > 20:
                lines.append(f"\n... and {len(result.adverse_events) - 20} more")

        return "\n".join(lines)

    @mcp.tool()
    async def drug_safety_score(drug: str, event: str) -> str:
        """Get the LRT (log-likelihood ratio) safety score for a drug-event pair.

        Returns the statistical association strength from OpenTargets Platform.

        Args:
            drug: Generic drug name (e.g., "propofol").
            event: Adverse event term (e.g., "bradycardia").
        """
        score = await opentargets_api.drug_safety_score(drug, event)

        if score is None:
            return (
                f"No OpenTargets LRT score found for {drug.upper()} + {event.upper()}. "
                f"The drug or event may not be in the OpenTargets database."
            )

        return (
            f"# OpenTargets Safety Score\n"
            f"**Drug:** {drug.upper()}\n"
            f"**Event:** {event.upper()}\n"
            f"**Log-LR:** {score:.4f}\n\n"
            f"A positive logLR indicates the event is reported more frequently "
            f"than expected. Higher values suggest stronger statistical association."
        )
