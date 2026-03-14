"""MCP tools para normalização de vocabulário."""

from __future__ import annotations

from typing import TYPE_CHECKING

from hypokrates.vocab import api as vocab_api

if TYPE_CHECKING:
    from mcp.server.fastmcp import FastMCP


def register(mcp: FastMCP) -> None:
    """Registra tools de vocab no MCP server."""

    @mcp.tool()
    async def normalize_drug(name: str) -> str:
        """Normalize a drug name to its generic equivalent via RxNorm.

        Resolves brand names (e.g., "Advil") to generic names (e.g., "ibuprofen").

        Args:
            name: Drug name (brand or generic).
        """
        result = await vocab_api.normalize_drug(name)

        lines: list[str] = [f"# Drug Normalization: {name}"]

        if result.generic_name:
            lines.append(f"**Generic name:** {result.generic_name}")
            if result.rxcui:
                lines.append(f"**RXCUI:** {result.rxcui}")
            if result.brand_names:
                lines.append(f"**Brand names:** {', '.join(result.brand_names)}")
        else:
            lines.append("No match found in RxNorm.")

        return "\n".join(lines)

    @mcp.tool()
    async def map_to_mesh(term: str) -> str:
        """Map a medical term to its MeSH heading via NCBI.

        Maps terms like "aspirin" to their controlled vocabulary (MeSH) equivalent.

        Args:
            term: Medical term to map.
        """
        result = await vocab_api.map_to_mesh(term)

        lines: list[str] = [f"# MeSH Mapping: {term}"]

        if result.mesh_term:
            lines.append(f"**MeSH term:** {result.mesh_term}")
            if result.mesh_id:
                lines.append(f"**MeSH ID:** {result.mesh_id}")
            if result.tree_numbers:
                lines.append(f"**Tree numbers:** {', '.join(result.tree_numbers)}")
        else:
            lines.append("No MeSH match found.")

        return "\n".join(lines)
