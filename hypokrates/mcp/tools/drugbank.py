from __future__ import annotations

from typing import TYPE_CHECKING

from hypokrates.drugbank import api as drugbank_api
from hypokrates.exceptions import HypokratesError

if TYPE_CHECKING:
    from mcp.server.fastmcp import FastMCP

_UNAVAILABLE_MSG = (
    "DrugBank not available: {}. Configure with configure(drugbank_path='/path/to/drugbank.xml')."
)


def register(mcp: FastMCP) -> None:
    @mcp.tool()
    async def drug_info(drug: str) -> str:
        """Get drug information from DrugBank (mechanism, targets, enzymes, interactions).

        Requires DrugBank XML to be configured via configure(drugbank_path=...).

        Args:
            drug: Generic drug name (e.g., "propofol").
        """
        try:
            info = await drugbank_api.drug_info(drug)
        except HypokratesError as exc:
            return _UNAVAILABLE_MSG.format(exc)
        except Exception as exc:
            return f"DrugBank error: {exc}"
        if info is None:
            return f"Drug '{drug}' not found in DrugBank."

        lines = [
            f"# DrugBank: {info.name}",
            f"**ID:** {info.drugbank_id}",
        ]

        if info.mechanism_of_action:
            moa = info.mechanism_of_action[:500]
            lines.extend(["", "## Mechanism of Action", moa])

        if info.targets:
            lines.extend(["", "## Targets"])
            for t in info.targets[:10]:
                actions = ", ".join(t.actions) if t.actions else "unknown"
                gene = f" ({t.gene_name})" if t.gene_name else ""
                lines.append(f"- {t.name}{gene} — {actions}")

        if info.enzymes:
            lines.extend(["", "## Metabolizing Enzymes"])
            for e in info.enzymes:
                gene = f" ({e.gene_name})" if e.gene_name else ""
                lines.append(f"- {e.name}{gene}")

        if info.interactions:
            count = len(info.interactions)
            lines.extend(["", f"## Interactions ({count} total)"])
            for it in info.interactions[:10]:
                desc = it.description[:100] if it.description else ""
                lines.append(f"- **{it.partner_name}**: {desc}")
            if count > 10:
                lines.append(f"... and {count - 10} more")

        return "\n".join(lines)

    @mcp.tool()
    async def drug_interactions(drug: str) -> str:
        """Get drug-drug interactions from DrugBank.

        Requires DrugBank XML to be configured via configure(drugbank_path=...).

        Args:
            drug: Generic drug name (e.g., "propofol").
        """
        try:
            interactions = await drugbank_api.drug_interactions(drug)
        except HypokratesError as exc:
            return _UNAVAILABLE_MSG.format(exc)
        except Exception as exc:
            return f"DrugBank error: {exc}"
        if not interactions:
            return f"No interactions found for '{drug}' in DrugBank."

        lines = [
            f"# Drug Interactions: {drug.upper()}",
            f"**Total:** {len(interactions)}",
            "",
        ]

        for it in interactions[:20]:
            desc = it.description[:150] if it.description else "No description"
            lines.append(f"- **{it.partner_name}** ({it.partner_id}): {desc}")

        if len(interactions) > 20:
            lines.append(f"\n... and {len(interactions) - 20} more")

        return "\n".join(lines)
