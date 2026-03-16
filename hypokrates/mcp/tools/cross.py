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
        check_chembl: bool = False,
        check_coadmin: bool = False,
        suspect_only: bool = False,
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
            check_chembl: Check ChEMBL for mechanism/targets (opt-in, no API key).
            check_coadmin: Check co-administration confounding (opt-in).
            suspect_only: Only count reports where drug is suspect (not concomitant).
        """
        result = await cross_api.hypothesis(
            drug,
            event,
            check_label=check_label,
            check_trials=check_trials,
            check_drugbank=check_drugbank,
            check_opentargets=check_opentargets,
            check_chembl=check_chembl,
            check_coadmin=check_coadmin,
            suspect_only=suspect_only,
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
        if result.coadmin is not None:
            lines.extend(["", "## Co-Administration Analysis"])
            lines.append(f"**Verdict:** {result.coadmin.verdict}")
            lines.append(
                f"**Median suspects/report:** {result.coadmin.profile.median_suspects:.1f}"
            )
            lines.append(
                f"**Co-admin flag:** {'YES' if result.coadmin.profile.co_admin_flag else 'NO'}"
            )
            lines.append(f"**Overlap ratio:** {result.coadmin.overlap_ratio:.2f}")
            if result.coadmin.specificity_ratio is not None:
                lines.append(f"**Specificity ratio:** {result.coadmin.specificity_ratio:.2f}")
            if result.coadmin.co_signals:
                lines.append("")
                lines.append("| Co-Drug | PRR | Signal |")
                lines.append("|---------|-----|--------|")
                for cs in result.coadmin.co_signals:
                    sig_str = "YES" if cs.signal_detected else "NO"
                    lines.append(f"| {cs.drug} | {cs.prr:.2f} | {sig_str} |")
            if result.coadmin.profile.co_admin_flag and result.coadmin.verdict != "specific":
                lines.extend(
                    [
                        "",
                        "**⚠ Co-admin confounding likely.** PRR may be inflated by "
                        "procedural co-administration, not causality.",
                    ]
                )
            elif result.coadmin.profile.co_admin_flag and result.coadmin.verdict == "specific":
                lines.extend(
                    [
                        "",
                        "**Co-admin detected but signal appears specific to this drug.**",
                    ]
                )
        if result.indication_confounding:
            lines.extend(
                [
                    "",
                    "**⚠ INDICATION CONFOUNDING:** This event matches a known "
                    "therapeutic indication. High PRR may reflect the patient "
                    "population, not drug toxicity.",
                ]
            )
        if result.articles:
            lines.append("")
            lines.append("## Articles")
            for art in result.articles:
                lines.append(f"- [{art.pmid}] {art.title}")
        lines.extend(
            [
                "",
                "---",
                "**Note:** PRR measures disproportionality of reporting, NOT absolute risk. "
                "Clinical significance requires validation with meta-analyses and guidelines.",
            ]
        )
        return "\n".join(lines)

    @mcp.tool()
    async def compare_signals(
        drug: str,
        control: str,
        events: str = "",
        top_n: int = 10,
        suspect_only: bool = False,
    ) -> str:
        """Compare disproportionality signals between two drugs (intra-class).

        Useful for separating genuine signal from confounding by indication
        (e.g., isotretinoin vs doxycycline in the same acne population).

        Args:
            drug: Primary drug name (e.g., "isotretinoin").
            control: Control drug from same class (e.g., "doxycycline").
            events: Comma-separated event names. If empty, auto-detects top events.
            top_n: Number of top events when auto-detecting.
            suspect_only: Only count reports where drug is suspect.
        """
        event_list: list[str] | None = None
        if events.strip():
            event_list = [e.strip() for e in events.split(",")]

        result = await cross_api.compare_signals(
            drug,
            control,
            events=event_list,
            top_n=top_n,
            suspect_only=suspect_only,
        )

        lines = [
            f"# Compare: {drug.upper()} vs {control.upper()}",
            f"**Events compared:** {result.total_events}",
            f"**Drug-only signals:** {result.drug_unique_signals}",
            f"**Control-only signals:** {result.control_unique_signals}",
            f"**Both detected:** {result.both_detected}",
            "",
        ]

        if result.items:
            lines.append("| Event | Drug PRR | Control PRR | Ratio | Stronger |")
            lines.append("|-------|----------|-------------|-------|----------|")
            for item in result.items:
                ratio_str = f"{item.ratio:.1f}x" if item.ratio != float("inf") else "inf"
                lines.append(
                    f"| {item.event} | {item.drug_prr:.2f} | "
                    f"{item.control_prr:.2f} | {ratio_str} | "
                    f"{item.stronger} |"
                )

        lines.extend(
            [
                "",
                "---",
                "**Note:** PRR ratio > 1 means drug has stronger signal than control. "
                "Does not imply causation.",
            ]
        )

        return "\n".join(lines)
