"""MCP tools para scan de eventos adversos."""

from __future__ import annotations

import logging
import time
from typing import TYPE_CHECKING

from hypokrates.scan import api as scan_api
from hypokrates.scan import class_compare as class_compare_api
from hypokrates.scan.models import EventClassification

if TYPE_CHECKING:
    from mcp.server.fastmcp import FastMCP

logger = logging.getLogger(__name__)


def register(mcp: FastMCP) -> None:
    """Registra tools de scan no MCP server."""

    @mcp.tool()
    async def scan_drug(
        drug: str,
        top_n: int = 10,
        check_labels: bool = False,
        check_trials: bool = False,
        check_drugbank: bool = False,
        check_opentargets: bool = False,
        check_chembl: bool = False,
        group_events: bool = True,
        filter_operational: bool = True,
        suspect_only: bool = False,
        use_bulk: bool | None = None,
    ) -> str:
        """Scan a drug's adverse events and classify each as novel/emerging/known signal.

        Runs hypothesis analysis for each of the top N adverse events reported in FAERS.
        This involves ~5 HTTP requests per event (4 FAERS + 1 PubMed).

        Operational/regulatory MedDRA terms (e.g., OFF LABEL USE, MEDICATION ERROR,
        DRUG INEFFECTIVE) are filtered by default to focus on biological signals.
        Items with >2000 FAERS reports are flagged as potential reporting artifacts.

        NOTE: This operation takes 1-3 minutes depending on top_n and API key availability.
        With API key: ~30-60s. Without: ~2-3 minutes.

        Args:
            drug: Generic drug name (e.g., "propofol").
            top_n: Number of top events to scan (max 20).
            check_labels: Check FDA label via DailyMed for each event (opt-in).
            check_trials: Search ClinicalTrials.gov for each event (opt-in).
            check_drugbank: Check DrugBank for mechanism/interactions (opt-in).
            check_opentargets: Check OpenTargets for LRT scores (opt-in).
            check_chembl: Check ChEMBL for mechanism/targets (opt-in, no API key).
            group_events: Group synonymous MedDRA terms (default True).
            filter_operational: Filter operational/regulatory MedDRA terms (default True).
            suspect_only: Only count reports where drug is suspect (not concomitant).
            use_bulk: None=auto-detect, true=force bulk, false=force API.
        """
        clamped_top_n = min(top_n, 20)
        start = time.monotonic()

        def _on_progress(completed: int, total: int, event: str) -> None:
            logger.info("MCP scan %s: %d/%d — %s", drug, completed, total, event)

        try:
            result = await scan_api.scan_drug(
                drug,
                top_n=clamped_top_n,
                check_labels=check_labels,
                check_trials=check_trials,
                check_drugbank=check_drugbank,
                check_opentargets=check_opentargets,
                check_chembl=check_chembl,
                group_events=group_events,
                filter_operational=filter_operational,
                suspect_only=suspect_only,
                use_bulk=use_bulk,
                on_progress=_on_progress,
            )
        except Exception as exc:
            elapsed = time.monotonic() - start
            logger.error("MCP scan %s failed after %.0fs: %s", drug, elapsed, exc)
            return f"# Scan: {drug.upper()}\n\nERROR after {elapsed:.0f}s: {exc}"

        elapsed = time.monotonic() - start

        lines: list[str] = [
            f"# Scan: {drug.upper()}",
            f"Scanned {result.total_scanned} events in {elapsed:.0f}s",
            "",
        ]

        if result.items:
            lines.append("## Results (ranked by score)")
            lines.append("")
            for item in result.items:
                prr_val = f"{item.signal.prr.value:.2f}"
                label_info = ""
                if item.in_label is not None:
                    label_info = f" | label={'YES' if item.in_label else 'NO'}"
                trials_info = ""
                if item.active_trials is not None:
                    trials_info = f" | trials={item.active_trials}"
                ot_info = ""
                if item.ot_llr is not None:
                    ot_info = f" | logLR={item.ot_llr:.2f}"
                grouped_info = ""
                if item.grouped_terms and len(item.grouped_terms) > 1:
                    grouped_info = f" (grouped: {', '.join(item.grouped_terms)})"
                vol_info = ""
                if item.volume_flag:
                    vol_info = " | ⚠ VOLUME"
                indication_info = ""
                if item.is_indication:
                    indication_info = " | ⚠ INDICATION"
                lines.append(
                    f"{item.rank}. **{item.event}** — "
                    f"{item.classification.value} | "
                    f"PRR={prr_val} | "
                    f"lit={item.literature_count}"
                    f"{label_info}{trials_info}{ot_info}"
                    f"{vol_info}{indication_info}"
                    f"{grouped_info}"
                )
            lines.append("")

            # Agrupar por cluster semântico
            clustered: dict[str, list[str]] = {}
            for item in result.items:
                cluster = item.cluster or "Other"
                if cluster not in clustered:
                    clustered[cluster] = []
                clustered[cluster].append(f"{item.event} (PRR={item.signal.prr.value:.1f})")

            if len(clustered) > 1 or (len(clustered) == 1 and "Other" not in clustered):
                lines.append("## By Clinical System")
                lines.append("")
                for cluster_name, event_summaries in clustered.items():
                    lines.append(f"**{cluster_name}:** {', '.join(event_summaries)}")
                lines.append("")

        if result.mechanism:
            lines.extend(["## Mechanism of Action", result.mechanism[:300], ""])

        if result.cyp_enzymes:
            lines.append(f"**CYP Enzymes:** {', '.join(result.cyp_enzymes)}")
            lines.append("")

        lines.append("## Summary")
        summary_parts = [
            f"{result.novel_count} novel",
            f"{result.emerging_count} emerging",
            f"{result.known_count} known",
            f"{result.no_signal_count} no signal",
        ]
        if result.labeled_count > 0:
            summary_parts.append(f"{result.labeled_count} in label")
        if result.filtered_operational_count > 0:
            summary_parts.append(f"{result.filtered_operational_count} operational filtered")
        if result.groups_applied:
            summary_parts.append("MedDRA grouped")
        if result.interactions_count is not None:
            summary_parts.append(f"{result.interactions_count} drug interactions")
        lines.append(", ".join(summary_parts))
        if result.failed_count > 0:
            lines.append(f"{result.failed_count} failed: {', '.join(result.skipped_events)}")

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
    async def compare_class(
        drugs: str,
        top_n: int = 30,
        suspect_only: bool = False,
    ) -> str:
        """Compare adverse event signals across drugs of the same therapeutic class.

        Classifies events as class_effect (>=75% drugs), drug_specific (1 drug),
        or differential (PRR outlier). Useful for separating class effects from
        drug-specific toxicity (e.g., prednisone vs dexamethasone vs methylprednisolone).

        Args:
            drugs: Comma-separated drug names (e.g., "prednisone,dexamethasone").
            top_n: Number of top events per drug to include in the union.
            suspect_only: Only count reports where drug is suspect (not concomitant).
        """
        drug_list = [d.strip() for d in drugs.split(",") if d.strip()]
        if len(drug_list) < 2:
            return "ERROR: At least 2 drugs required (comma-separated)."

        start = time.monotonic()
        try:
            result = await class_compare_api.compare_class(
                drug_list,
                top_n=top_n,
                suspect_only=suspect_only,
            )
        except Exception as exc:
            elapsed = time.monotonic() - start
            logger.error("MCP compare_class failed after %.0fs: %s", elapsed, exc)
            return f"# Compare Class\n\nERROR after {elapsed:.0f}s: {exc}"

        elapsed = time.monotonic() - start
        drug_header = ", ".join(d.upper() for d in drug_list)

        lines: list[str] = [
            f"# Class Comparison: {drug_header}",
            f"Compared {result.total_events} events across "
            f"{len(drug_list)} drugs in {elapsed:.0f}s",
            "",
        ]

        # Class Effects
        class_items = [
            it for it in result.items if it.classification == EventClassification.CLASS_EFFECT
        ]
        if class_items:
            lines.append(f"## Class Effects ({len(class_items)})")
            lines.append("")
            header = "| Event |" + "|".join(f" {d.upper()} " for d in drug_list) + "|"
            sep = "|-------|" + "|".join("------:" for _ in drug_list) + "|"
            lines.extend([header, sep])
            for item in class_items:
                prr_cols = "|".join(f" {item.prr_values.get(d, 0.0):.1f} " for d in drug_list)
                lines.append(f"| {item.event} |{prr_cols}|")
            lines.append("")

        # Drug-Specific
        specific_items = [
            it for it in result.items if it.classification == EventClassification.DRUG_SPECIFIC
        ]
        if specific_items:
            lines.append(f"## Drug-Specific ({len(specific_items)})")
            lines.append("")
            for item in specific_items:
                drug_name = item.drugs_with_signal[0] if item.drugs_with_signal else "?"
                lines.append(
                    f"- **{item.event}** — {drug_name.upper()} only (PRR={item.max_prr:.1f})"
                )
            lines.append("")

        # Differential
        diff_items = [
            it for it in result.items if it.classification == EventClassification.DIFFERENTIAL
        ]
        if diff_items:
            lines.append(f"## Differential ({len(diff_items)})")
            lines.append("")
            header = "| Event |" + "|".join(f" {d.upper()} " for d in drug_list) + "| Note |"
            sep = "|-------|" + "|".join("------:" for _ in drug_list) + "|------|"
            lines.extend([header, sep])
            for item in diff_items:
                prr_cols = "|".join(f" {item.prr_values.get(d, 0.0):.1f} " for d in drug_list)
                note = ""
                if item.outlier_drug:
                    note = f"{item.outlier_drug.upper()} {item.outlier_factor:.1f}x median"
                else:
                    with_str = ", ".join(d.upper() for d in item.drugs_with_signal)
                    note = f"signal in: {with_str}"
                lines.append(f"| {item.event} |{prr_cols}| {note} |")
            lines.append("")

        # Summary
        lines.append("## Summary")
        lines.append(
            f"{result.class_effect_count} class effects, "
            f"{result.drug_specific_count} drug-specific, "
            f"{result.differential_count} differential"
        )

        lines.extend(
            [
                "",
                "---",
                "**Note:** PRR measures disproportionality of reporting, NOT absolute risk. "
                "Clinical significance requires validation with meta-analyses and guidelines.",
            ]
        )

        return "\n".join(lines)
