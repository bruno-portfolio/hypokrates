from __future__ import annotations

from typing import TYPE_CHECKING

from hypokrates.constants import __version__

if TYPE_CHECKING:
    from mcp.server.fastmcp import FastMCP

_TOOLS = [
    {"name": "adverse_events", "module": "faers", "description": "Search FAERS adverse events"},
    {"name": "top_events", "module": "faers", "description": "Get top adverse events"},
    {"name": "drugs_by_event", "module": "faers", "description": "Reverse lookup: drugs by event"},
    {"name": "co_suspect_profile", "module": "faers", "description": "Co-administration patterns"},
    {"name": "compare_drugs", "module": "faers", "description": "Compare drugs"},
    {"name": "signal", "module": "stats", "description": "Disproportionality signal detection"},
    {
        "name": "batch_signal",
        "module": "stats",
        "description": "Batch signal detection (multiple pairs)",
    },
    {"name": "signal_timeline", "module": "stats", "description": "Temporal analysis"},
    {"name": "count_papers", "module": "pubmed", "description": "Count PubMed papers"},
    {"name": "search_papers", "module": "pubmed", "description": "Search PubMed papers"},
    {"name": "hypothesis", "module": "cross", "description": "Cross-reference hypothesis"},
    {"name": "compare_signals", "module": "cross", "description": "Compare two drugs"},
    {"name": "scan_drug", "module": "scan", "description": "Scan drug adverse events"},
    {"name": "compare_class", "module": "scan", "description": "Compare intra-class AE signals"},
    {"name": "normalize_drug", "module": "vocab", "description": "Normalize drug name via RxNorm"},
    {"name": "map_to_mesh", "module": "vocab", "description": "Map term to MeSH heading"},
    {"name": "label_events", "module": "dailymed", "description": "FDA label adverse reactions"},
    {"name": "check_label", "module": "dailymed", "description": "Check event in drug label"},
    {"name": "search_trials", "module": "trials", "description": "Search clinical trials"},
    {"name": "drug_info", "module": "drugbank", "description": "DrugBank drug info"},
    {"name": "drug_interactions", "module": "drugbank", "description": "DrugBank interactions"},
    {"name": "drug_adverse_events", "module": "opentargets", "description": "OpenTargets AEs"},
    {"name": "drug_safety_score", "module": "opentargets", "description": "OpenTargets LRT score"},
    {"name": "drug_mechanism", "module": "chembl", "description": "ChEMBL mechanism of action"},
    {"name": "drug_metabolism", "module": "chembl", "description": "ChEMBL metabolic pathways"},
    {
        "name": "faers_bulk_status",
        "module": "faers_bulk",
        "description": "FAERS Bulk store status",
    },
    {
        "name": "faers_bulk_signal",
        "module": "faers_bulk",
        "description": "Signal via FAERS Bulk (deduplicated)",
    },
    {
        "name": "faers_bulk_load",
        "module": "faers_bulk",
        "description": "Load FAERS quarterly ZIPs",
    },
    {
        "name": "faers_bulk_timeline",
        "module": "faers_bulk",
        "description": "Quarterly timeline via FAERS Bulk",
    },
    {
        "name": "anvisa_buscar",
        "module": "anvisa",
        "description": "Search Brazilian drug registry (ANVISA)",
    },
    {
        "name": "anvisa_genericos",
        "module": "anvisa",
        "description": "List generics/similars (ANVISA)",
    },
    {
        "name": "anvisa_mapear_nome",
        "module": "anvisa",
        "description": "Map PT↔EN drug names",
    },
    {
        "name": "onsides_events",
        "module": "onsides",
        "description": "International label AEs via OnSIDES (NLP)",
    },
    {
        "name": "onsides_check_event",
        "module": "onsides",
        "description": "Check event in international labels",
    },
    {
        "name": "pgx_drug_info",
        "module": "pharmgkb",
        "description": "PharmGKB pharmacogenomic info",
    },
    {
        "name": "pgx_annotations",
        "module": "pharmgkb",
        "description": "PharmGKB clinical annotations",
    },
    {
        "name": "pgx_guidelines",
        "module": "pharmgkb",
        "description": "PharmGKB dosing guidelines (CPIC/DPWG)",
    },
    {
        "name": "canada_signal",
        "module": "canada",
        "description": "PRR signal in Canada Vigilance",
    },
    {
        "name": "canada_top_events",
        "module": "canada",
        "description": "Top AEs in Canada Vigilance",
    },
    {
        "name": "canada_bulk_status",
        "module": "canada",
        "description": "Canada Vigilance store status",
    },
    {
        "name": "jader_signal",
        "module": "jader",
        "description": "PRR signal in JADER (Japan)",
    },
    {
        "name": "jader_top_events",
        "module": "jader",
        "description": "Top AEs in JADER (Japan)",
    },
    {
        "name": "jader_bulk_status",
        "module": "jader",
        "description": "JADER store status",
    },
    {
        "name": "investigate",
        "module": "cross",
        "description": "Deep investigation with demographic stratification",
    },
    {"name": "list_tools", "module": "meta", "description": "List available tools"},
    {"name": "version", "module": "meta", "description": "Show version info"},
]


def register(mcp: FastMCP) -> None:
    @mcp.tool()
    async def list_tools() -> str:
        """List all available hypokrates MCP tools."""
        lines = [f"# hypokrates MCP Tools (Sprint 11 — {len(_TOOLS)} tools)", ""]
        for tool in _TOOLS:
            lines.append(f"- **{tool['name']}** ({tool['module']}): {tool['description']}")
        return "\n".join(lines)

    @mcp.tool()
    async def version() -> str:
        """Show hypokrates version and sprint info."""
        return (
            f"# hypokrates {__version__}\n"
            f"**Sprint:** 11 (JADER + Stratification + AGPL + Benchmark)\n"
            f"**Tools:** {len(_TOOLS)}\n"
            f"**Modules:** faers, stats, pubmed, cross, scan, vocab, "
            f"dailymed, trials, drugbank, opentargets, chembl, faers_bulk, "
            f"anvisa, onsides, pharmgkb, canada, jader, meta\n"
        )
