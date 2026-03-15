"""MCP tools para ANVISA."""

from __future__ import annotations

from typing import TYPE_CHECKING

from hypokrates.anvisa import api as anvisa_api

if TYPE_CHECKING:
    from mcp.server.fastmcp import FastMCP


def register(mcp: FastMCP) -> None:
    """Registra tools de ANVISA no MCP server."""

    @mcp.tool()
    async def anvisa_buscar(nome: str) -> str:
        """Search Brazilian drug registry (ANVISA) by brand name or active ingredient.

        Returns registered products with: name, active ingredient, category
        (generic/reference/similar), ATC code, manufacturer, presentations.
        Supports partial matching and Portuguese-English name mapping.
        Data source: ANVISA open data (CC BY-ND 3.0).

        Args:
            nome: Drug name or active ingredient (Portuguese or English).
        """
        result = await anvisa_api.buscar_medicamento(nome, limit=15)
        if not result.medicamentos:
            return f"Nenhum medicamento encontrado para '{nome}' na ANVISA."

        lines = [
            f"# ANVISA: Busca por '{nome}'",
            f"**Resultados:** {result.total}",
            "",
        ]

        for med in result.medicamentos:
            subs = ", ".join(med.substancias) if med.substancias else "—"
            lines.append(f"### {med.nome_produto}")
            lines.append(f"- **Substancia(s):** {subs}")
            if med.categoria:
                lines.append(f"- **Categoria:** {med.categoria}")
            if med.referencia:
                lines.append(f"- **Referencia:** {med.referencia}")
            if med.empresa:
                lines.append(f"- **Fabricante:** {med.empresa}")
            if med.atc:
                lines.append(f"- **ATC:** {med.atc}")
            if med.apresentacoes:
                apres = "; ".join(med.apresentacoes[:5])
                lines.append(f"- **Apresentacoes:** {apres}")
                if len(med.apresentacoes) > 5:
                    lines.append(f"  ... e mais {len(med.apresentacoes) - 5}")
            lines.append(f"- **Registro:** {med.registro}")
            lines.append("")

        lines.append("---")
        lines.append("*Fonte: ANVISA — Agencia Nacional de Vigilancia Sanitaria*")
        return "\n".join(lines)

    @mcp.tool()
    async def anvisa_genericos(substancia: str) -> str:
        """List all generic/similar drugs registered in Brazil for an active ingredient.

        Useful for finding Brazilian equivalents of international drugs.

        Args:
            substancia: Active ingredient name (e.g., "metformina" or "metformin").
        """
        result = await anvisa_api.buscar_por_substancia(substancia, limit=30)
        if not result.medicamentos:
            return f"Nenhum medicamento com '{substancia}' encontrado na ANVISA."

        # Agrupar por categoria
        by_cat: dict[str, list[str]] = {}
        for med in result.medicamentos:
            cat = med.categoria or "Sem categoria"
            by_cat.setdefault(cat, []).append(
                f"{med.nome_produto} ({med.empresa})" if med.empresa else med.nome_produto
            )

        lines = [
            f"# ANVISA: Genericos/Similares de '{substancia}'",
            f"**Total:** {result.total} produtos registrados",
            "",
        ]

        for cat in sorted(by_cat):
            names = by_cat[cat]
            lines.append(f"## {cat} ({len(names)})")
            for name in names[:15]:
                lines.append(f"- {name}")
            if len(names) > 15:
                lines.append(f"... e mais {len(names) - 15}")
            lines.append("")

        lines.append("---")
        lines.append("*Fonte: ANVISA — Agencia Nacional de Vigilancia Sanitaria*")
        return "\n".join(lines)

    @mcp.tool()
    async def anvisa_mapear_nome(nome: str) -> str:
        """Map Brazilian drug name to international name (or vice-versa).

        Examples: dipirona -> metamizole, paracetamol -> acetaminophen,
        cetamina -> ketamine.

        Args:
            nome: Drug name in Portuguese or English.
        """
        mapping = await anvisa_api.mapear_nome(nome)
        if mapping is None:
            return (
                f"Mapeamento nao encontrado para '{nome}'.\n"
                "Tente com o nome completo (ex: 'dipirona sodica')."
            )

        lines = [
            f"# Mapeamento: {nome.upper()}",
            "",
            f"- **Portugues (BR):** {mapping.nome_pt}",
            f"- **Internacional (EN):** {mapping.nome_en}",
            f"- **Fonte:** {mapping.source}",
        ]
        return "\n".join(lines)
