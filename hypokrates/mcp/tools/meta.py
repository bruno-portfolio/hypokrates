"""MCP tools de metadados."""

from __future__ import annotations

from typing import TYPE_CHECKING

from hypokrates.constants import __version__

if TYPE_CHECKING:
    from mcp.server.fastmcp import FastMCP

_TOOLS = [
    {"name": "adverse_events", "module": "faers", "description": "Search FAERS adverse events"},
    {"name": "top_events", "module": "faers", "description": "Get top adverse events"},
    {"name": "compare_drugs", "module": "faers", "description": "Compare drugs"},
    {"name": "signal", "module": "stats", "description": "Disproportionality signal detection"},
    {"name": "count_papers", "module": "pubmed", "description": "Count PubMed papers"},
    {"name": "search_papers", "module": "pubmed", "description": "Search PubMed papers"},
    {"name": "hypothesis", "module": "cross", "description": "Cross-reference hypothesis"},
    {"name": "scan_drug", "module": "scan", "description": "Scan drug adverse events"},
    {"name": "normalize_drug", "module": "vocab", "description": "Normalize drug name via RxNorm"},
    {"name": "map_to_mesh", "module": "vocab", "description": "Map term to MeSH heading"},
    {"name": "list_tools", "module": "meta", "description": "List available tools"},
    {"name": "version", "module": "meta", "description": "Show version info"},
]


def register(mcp: FastMCP) -> None:
    """Registra tools de metadados no MCP server."""

    @mcp.tool()
    async def list_tools() -> str:
        """List all available hypokrates MCP tools."""
        lines = [f"# hypokrates MCP Tools (Sprint 4 — {len(_TOOLS)} tools)", ""]
        for tool in _TOOLS:
            lines.append(f"- **{tool['name']}** ({tool['module']}): {tool['description']}")
        return "\n".join(lines)

    @mcp.tool()
    async def version() -> str:
        """Show hypokrates version and sprint info."""
        return (
            f"# hypokrates {__version__}\n"
            f"**Sprint:** 4 (scan + vocab)\n"
            f"**Tools:** {len(_TOOLS)}\n"
            f"**Modules:** faers, stats, pubmed, cross, scan, vocab, meta\n"
        )
