"""MCP tools para PubMed."""

from __future__ import annotations

from typing import TYPE_CHECKING

from hypokrates.pubmed import api as pubmed_api

if TYPE_CHECKING:
    from mcp.server.fastmcp import FastMCP


def register(mcp: FastMCP) -> None:
    """Registra tools PubMed no MCP server."""

    @mcp.tool()
    async def count_papers(drug: str, event: str) -> str:
        """Count PubMed papers mentioning a drug-event pair.

        Args:
            drug: Drug name.
            event: Adverse event term.
        """
        result = await pubmed_api.count_papers(drug, event)
        return f"# PubMed Count: {drug} + {event}\n**Total papers:** {result.total_count}\n"

    @mcp.tool()
    async def search_papers(drug: str, event: str, limit: int = 5) -> str:
        """Search PubMed for papers about a drug-event pair.

        Args:
            drug: Drug name.
            event: Adverse event term.
            limit: Max articles to return.
        """
        result = await pubmed_api.search_papers(drug, event, limit=limit)
        lines = [
            f"# PubMed Search: {drug} + {event}",
            f"**Total:** {result.total_count} papers",
            "",
        ]
        for art in result.articles:
            doi = f" | doi:{art.doi}" if art.doi else ""
            lines.append(f"- [{art.pmid}] {art.title}{doi}")
            if art.abstract:
                snippet = art.abstract[:200] + "..." if len(art.abstract) > 200 else art.abstract
                lines.append(f"  > {snippet}")
        return "\n".join(lines)
