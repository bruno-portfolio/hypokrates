"""MCP tools para scan de eventos adversos."""

from __future__ import annotations

import logging
import time
from typing import TYPE_CHECKING

from hypokrates.scan import api as scan_api

if TYPE_CHECKING:
    from mcp.server.fastmcp import FastMCP

logger = logging.getLogger(__name__)


def register(mcp: FastMCP) -> None:
    """Registra tools de scan no MCP server."""

    @mcp.tool()
    async def scan_drug(drug: str, top_n: int = 10) -> str:
        """Scan a drug's adverse events and classify each as novel/emerging/known signal.

        Runs hypothesis analysis for each of the top N adverse events reported in FAERS.
        This involves ~5 HTTP requests per event (4 FAERS + 1 PubMed).

        NOTE: This operation takes 1-3 minutes depending on top_n and API key availability.
        With API key: ~30-60s. Without: ~2-3 minutes.

        Args:
            drug: Generic drug name (e.g., "propofol").
            top_n: Number of top events to scan (max 20).
        """
        clamped_top_n = min(top_n, 20)
        start = time.monotonic()

        def _on_progress(completed: int, total: int, event: str) -> None:
            logger.info("MCP scan %s: %d/%d — %s", drug, completed, total, event)

        result = await scan_api.scan_drug(
            drug,
            top_n=clamped_top_n,
            on_progress=_on_progress,
        )

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
                lines.append(
                    f"{item.rank}. **{item.event}** — "
                    f"{item.classification.value} | "
                    f"PRR={prr_val} | "
                    f"lit={item.literature_count}"
                )
            lines.append("")

        lines.append("## Summary")
        lines.append(
            f"{result.novel_count} novel, "
            f"{result.emerging_count} emerging, "
            f"{result.known_count} known, "
            f"{result.no_signal_count} no signal"
        )
        if result.failed_count > 0:
            lines.append(f"{result.failed_count} failed: {', '.join(result.skipped_events)}")

        return "\n".join(lines)
