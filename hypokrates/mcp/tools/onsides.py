from __future__ import annotations

from typing import TYPE_CHECKING

from hypokrates.exceptions import HypokratesError
from hypokrates.onsides import api as onsides_api

if TYPE_CHECKING:
    from mcp.server.fastmcp import FastMCP

_UNAVAILABLE_MSG = (
    "OnSIDES not available: {}. Configure with configure(onsides_path='/path/to/onsides/csvs/')."
)


def register(mcp: FastMCP) -> None:
    @mcp.tool()
    async def onsides_events(
        drug: str,
        min_confidence: float = 0.5,
    ) -> str:
        """Get adverse events from international drug labels via OnSIDES (NLP-extracted).

        OnSIDES contains 7.1M drug-ADE pairs extracted by PubMedBERT from 51,460
        drug labels across 4 countries (US, EU, UK, JP). F1=0.935.

        Requires OnSIDES CSVs to be configured via configure(onsides_path=...).

        Args:
            drug: Generic drug name (e.g., "propofol").
            min_confidence: Minimum prediction confidence (0-1, default 0.5).
        """
        try:
            result = await onsides_api.onsides_events(drug, min_confidence=min_confidence)
        except HypokratesError as exc:
            return _UNAVAILABLE_MSG.format(exc)
        except Exception as exc:
            return f"OnSIDES error: {exc}"

        if not result.events:
            return f"No events found for '{drug}' in OnSIDES (min_confidence={min_confidence})."

        lines = [
            f"# OnSIDES: {drug.upper()}",
            f"**Total events:** {result.total_events}",
            "",
            "| Event | Section | Confidence | Sources |",
            "|-------|---------|------------|---------|",
        ]

        for ev in result.events[:30]:
            sources_str = ", ".join(ev.sources)
            lines.append(
                f"| {ev.meddra_name} | {ev.label_section} | "
                f"{ev.confidence:.3f} | {sources_str} ({ev.num_sources}/4) |"
            )

        if result.total_events > 30:
            lines.append(f"\n... and {result.total_events - 30} more")

        lines.extend(
            [
                "",
                "---",
                "**Note:** Confidence scores are from PubMedBERT NLP extraction. "
                "Sources indicate countries where the ADE appears in official labels.",
            ]
        )

        return "\n".join(lines)

    @mcp.tool()
    async def onsides_check_event(drug: str, event: str) -> str:
        """Check if a specific adverse event is listed in international drug labels.

        Uses OnSIDES database (NLP-extracted from US/EU/UK/JP labels).

        Args:
            drug: Generic drug name (e.g., "propofol").
            event: Adverse event term (e.g., "bradycardia").
        """
        try:
            result = await onsides_api.onsides_check_event(drug, event)
        except HypokratesError as exc:
            return _UNAVAILABLE_MSG.format(exc)
        except Exception as exc:
            return f"OnSIDES error: {exc}"

        if result is None:
            return (
                f"Event '{event}' NOT found in OnSIDES labels for '{drug}'.\n"
                "The event may not be listed in any of the 4 country labels "
                "(US, EU, UK, JP) or confidence was below threshold."
            )

        sources_str = ", ".join(result.sources)
        return (
            f"# OnSIDES: {drug.upper()} + {event.upper()}\n"
            f"**Found:** YES\n"
            f"**MedDRA ID:** {result.meddra_id}\n"
            f"**Section:** {result.label_section}\n"
            f"**Confidence:** {result.confidence:.3f}\n"
            f"**Sources:** {sources_str} ({result.num_sources}/4 countries)"
        )
