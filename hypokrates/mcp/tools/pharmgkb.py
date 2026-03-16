"""MCP tools para PharmGKB."""

from __future__ import annotations

from typing import TYPE_CHECKING

from hypokrates.pharmgkb import api as pharmgkb_api

if TYPE_CHECKING:
    from mcp.server.fastmcp import FastMCP


def register(mcp: FastMCP) -> None:
    """Registra tools de PharmGKB no MCP server."""

    @mcp.tool()
    async def pgx_drug_info(drug: str) -> str:
        """Get pharmacogenomic information from PharmGKB (gene-drug associations, guidelines).

        Returns clinical annotations (gene variants affecting drug response)
        and dosing guidelines (CPIC, DPWG) for a drug.

        Args:
            drug: Generic drug name (e.g., "warfarin", "propofol").
        """
        try:
            result = await pharmgkb_api.pgx_drug_info(drug)
        except Exception as exc:
            return f"PharmGKB error: {exc}"

        if not result.annotations and not result.guidelines:
            return f"No pharmacogenomic data found for '{drug}' in PharmGKB."

        lines = [
            f"# PharmGKB: {drug.upper()}",
        ]

        if result.pharmgkb_id:
            lines.append(f"**PharmGKB ID:** {result.pharmgkb_id}")

        if result.annotations:
            lines.extend(["", f"## Clinical Annotations ({len(result.annotations)})"])
            lines.append("")
            lines.append("| Gene | Evidence | Categories |")
            lines.append("|------|----------|------------|")
            for ann in result.annotations[:20]:
                cats = ", ".join(ann.annotation_types[:3]) if ann.annotation_types else "-"
                lines.append(f"| {ann.gene_symbol} | {ann.level_of_evidence} | {cats} |")
            if len(result.annotations) > 20:
                lines.append(f"\n... and {len(result.annotations) - 20} more")

        if result.guidelines:
            lines.extend(["", f"## Dosing Guidelines ({len(result.guidelines)})"])
            for gl in result.guidelines:
                genes_str = ", ".join(gl.genes) if gl.genes else "N/A"
                lines.append(f"- **{gl.source}** — {gl.name} (genes: {genes_str})")
                if gl.summary:
                    lines.append(f"  {gl.summary[:200]}")

        lines.extend(
            [
                "",
                "---",
                "**Note:** Evidence levels: 1A (strongest, guideline-annotated) to "
                "4 (case report). Clinical implementation requires validated genotyping.",
            ]
        )

        return "\n".join(lines)

    @mcp.tool()
    async def pgx_guidelines(drug: str) -> str:
        """Get pharmacogenomic dosing guidelines (CPIC, DPWG) for a drug.

        Returns clinical dosing guidelines with gene-drug recommendations
        from organizations like CPIC and DPWG.

        Args:
            drug: Generic drug name (e.g., "warfarin", "codeine").
        """
        try:
            guidelines = await pharmgkb_api.pgx_guidelines(drug)
        except Exception as exc:
            return f"PharmGKB error: {exc}"

        if not guidelines:
            return f"No dosing guidelines found for '{drug}' in PharmGKB."

        lines = [
            f"# PharmGKB Dosing Guidelines: {drug.upper()}",
            f"**Total:** {len(guidelines)}",
            "",
        ]

        for gl in guidelines:
            genes_str = ", ".join(gl.genes) if gl.genes else "N/A"
            rec = "Yes" if gl.recommendation else "No"
            lines.append(f"### {gl.name}")
            lines.append(f"- **Source:** {gl.source}")
            lines.append(f"- **Genes:** {genes_str}")
            lines.append(f"- **Has recommendation:** {rec}")
            if gl.summary:
                lines.append(f"- **Summary:** {gl.summary[:300]}")
            lines.append("")

        lines.extend(
            [
                "---",
                "**Note:** Guidelines require validated genotyping before "
                "clinical implementation. See PharmGKB for full text.",
            ]
        )

        return "\n".join(lines)

    @mcp.tool()
    async def pgx_annotations(drug: str, min_level: str = "3") -> str:
        """Get clinical pharmacogenomic annotations for a drug.

        Returns gene-drug associations with evidence levels from PharmGKB.

        Args:
            drug: Generic drug name (e.g., "warfarin").
            min_level: Minimum evidence level (1A/1B/2A/2B/3/4, default "3").
        """
        try:
            annotations = await pharmgkb_api.pgx_annotations(drug, min_level=min_level)
        except Exception as exc:
            return f"PharmGKB error: {exc}"

        if not annotations:
            return (
                f"No pharmacogenomic annotations found for '{drug}' "
                f"at evidence level >= {min_level}."
            )

        lines = [
            f"# PharmGKB Annotations: {drug.upper()}",
            f"**Total:** {len(annotations)} (min level: {min_level})",
            "",
            "| Gene | Level | Categories | Score |",
            "|------|-------|------------|-------|",
        ]

        for ann in annotations[:30]:
            cats = ", ".join(ann.annotation_types[:3]) if ann.annotation_types else "-"
            lines.append(
                f"| {ann.gene_symbol} | {ann.level_of_evidence} | {cats} | {ann.score:.1f} |"
            )

        return "\n".join(lines)
