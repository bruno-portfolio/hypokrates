"""Construção de queries para busca no PubMed."""

from __future__ import annotations


def build_search_term(drug: str, event: str, *, use_mesh: bool = False) -> str:
    """Constrói termo de busca PubMed.

    Args:
        drug: Nome da droga.
        event: Termo do evento adverso.
        use_mesh: Se True, usa qualificadores MeSH (ex: "propofol"[MeSH]).
                  Se False, busca em texto livre (All Fields).

    Nota: A qualidade do cruzamento melhora significativamente com MeSH.
    Quando vocab/ estiver disponível (sprint futuro), este módulo poderá
    fazer mapping automático de termos livres para MeSH headings.
    """
    if use_mesh:
        return f'"{drug}"[MeSH] AND "{event}"[MeSH]'
    return f"{drug} AND {event}"
