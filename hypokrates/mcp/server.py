"""MCP server — ponto de entrada."""

from __future__ import annotations

from mcp.server.fastmcp import FastMCP

from hypokrates.mcp.tools import (
    chembl,
    cross,
    dailymed,
    drugbank,
    faers,
    faers_bulk,
    meta,
    opentargets,
    pubmed,
    scan,
    stats,
    trials,
    vocab,
)

mcp = FastMCP("hypokrates")


def create_server() -> FastMCP:
    """Cria e configura o MCP server com todas as tools."""
    faers.register(mcp)
    stats.register(mcp)
    pubmed.register(mcp)
    cross.register(mcp)
    meta.register(mcp)
    scan.register(mcp)
    vocab.register(mcp)
    dailymed.register(mcp)
    trials.register(mcp)
    drugbank.register(mcp)
    opentargets.register(mcp)
    chembl.register(mcp)
    faers_bulk.register(mcp)
    return mcp
