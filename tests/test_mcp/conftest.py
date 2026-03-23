"""Fixtures compartilhadas para testes MCP tools."""

from __future__ import annotations

from typing import Any

import pytest


class ToolCapture:
    """Captura tools registradas via @mcp.tool()."""

    def __init__(self) -> None:
        self.tools: dict[str, Any] = {}

    def tool(self) -> Any:
        def decorator(fn: Any) -> Any:
            self.tools[fn.__name__] = fn
            return fn

        return decorator


@pytest.fixture
def tool_capture() -> Any:
    """Factory fixture: retorna função que registra módulo e devolve ToolCapture."""

    def _capture(module: Any) -> ToolCapture:
        cap = ToolCapture()
        module.register(cap)
        return cap

    return _capture
