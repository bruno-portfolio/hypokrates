"""Entrypoint para o MCP server."""

from hypokrates.mcp.server import create_server

mcp = create_server()
mcp.run()
