"""MCP tools para cross-reference de hipóteses."""

from __future__ import annotations

from typing import TYPE_CHECKING

from hypokrates.cross import api as cross_api

if TYPE_CHECKING:
    from mcp.server.fastmcp import FastMCP


def register(mcp: FastMCP) -> None:
    """Registra tools de cross-reference no MCP server."""

    @mcp.tool()
    async def hypothesis(
        drug: str,
        event: str,
        check_label: bool = False,
        check_trials: bool = False,
        check_drugbank: bool = False,
        check_opentargets: bool = False,
    ) -> str:
        """Cross-reference FAERS signal with PubMed literature for a drug-event pair.

        Classifies the pair as novel_hypothesis, emerging_signal, known_association,
        or no_signal based on disproportionality analysis and literature count.

        Args:
            drug: Generic drug name.
            event: Adverse event term.
            check_label: Check FDA label via DailyMed (opt-in).
            check_trials: Search ClinicalTrials.gov (opt-in).
            check_drugbank: Check DrugBank for mechanism/interactions (opt-in).
            check_opentargets: Check OpenTargets for LRT score (opt-in).
        """
        result = await cross_api.hypothesis(
            drug,
            event,
            check_label=check_label,
            check_trials=check_trials,
            check_drugbank=check_drugbank,
            check_opentargets=check_opentargets,
        )
        lines = [
            f"# Hypothesis: {drug.upper()} + {event.upper()}",
            f"**Classification:** {result.classification.value}",
            f"**Signal detected:** {'YES' if result.signal.signal_detected else 'NO'}",
            f"**Literature count:** {result.literature_count}",
        ]
        if result.in_label is not None:
            lines.append(f"**In FDA label:** {'YES' if result.in_label else 'NO'}")
        if result.active_trials is not None:
            lines.append(f"**Active trials:** {result.active_trials}")
        lines.extend(["", "## Summary", result.summary])
        if result.label_detail:
            lines.extend(["", f"**Label detail:** {result.label_detail}"])
        if result.trials_detail:
            lines.append(f"**Trials detail:** {result.trials_detail}")
        if result.mechanism:
            lines.extend(["", f"**Mechanism:** {result.mechanism[:200]}"])
        if result.enzymes:
            lines.append(f"**CYP enzymes:** {', '.join(result.enzymes)}")
        if result.ot_llr is not None:
            lines.append(f"**OpenTargets logLR:** {result.ot_llr:.4f}")
        if result.articles:
            lines.append("")
            lines.append("## Articles")
            for art in result.articles:
                lines.append(f"- [{art.pmid}] {art.title}")
        return "\n".join(lines)
