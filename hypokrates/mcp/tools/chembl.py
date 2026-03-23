from __future__ import annotations

from typing import TYPE_CHECKING

from hypokrates.chembl import api as chembl_api

if TYPE_CHECKING:
    from mcp.server.fastmcp import FastMCP


def register(mcp: FastMCP) -> None:
    @mcp.tool()
    async def drug_mechanism(drug: str) -> str:
        """Get mechanism of action and targets from ChEMBL (free, no API key).

        Returns mechanism of action, action type, and target gene names.

        Args:
            drug: Generic drug name (e.g., "propofol").
        """
        result = await chembl_api.drug_mechanism(drug)

        if not result.chembl_id:
            return f"Drug '{drug}' not found in ChEMBL."

        lines = [
            f"# ChEMBL: {result.drug_name}",
            f"**ChEMBL ID:** {result.chembl_id}",
        ]

        if result.mechanism_of_action:
            lines.append(f"**Mechanism:** {result.mechanism_of_action}")
        if result.action_type:
            lines.append(f"**Action type:** {result.action_type}")
        if result.max_phase:
            lines.append(f"**Max phase:** {result.max_phase}")

        if result.targets:
            lines.extend(["", "## Targets"])
            for t in result.targets:
                genes = ", ".join(t.gene_names[:10]) if t.gene_names else "—"
                lines.append(f"- **{t.name}** ({t.organism}): {genes}")

        return "\n".join(lines)

    @mcp.tool()
    async def drug_metabolism(drug: str) -> str:
        """Get metabolic pathways and enzymes from ChEMBL (free, no API key).

        Returns metabolizing enzymes, conversions, and metabolite names.

        Args:
            drug: Generic drug name (e.g., "propofol").
        """
        result = await chembl_api.drug_metabolism(drug)

        if not result.chembl_id:
            return f"Drug '{drug}' not found in ChEMBL."

        lines = [
            f"# ChEMBL Metabolism: {result.drug_name}",
            f"**ChEMBL ID:** {result.chembl_id}",
            f"**Pathways:** {len(result.pathways)}",
        ]

        if result.pathways:
            lines.extend(["", "## Metabolic Pathways"])
            for p in result.pathways:
                enzyme = p.enzyme_name or "unknown enzyme"
                conv = p.conversion or "—"
                lines.append(f"- {p.substrate_name} → {p.metabolite_name} ({conv}, via {enzyme})")

        if not result.pathways:
            lines.append("\nNo metabolism data available for this drug.")

        return "\n".join(lines)
