"""Helpers compartilhados entre MCP tools."""

from __future__ import annotations

import re
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from hypokrates.cross.models import StratumSignal
    from hypokrates.pubmed.models import PubMedArticle

_ABSTRACT_SNIPPET_LEN = 200
_YEAR_RE = re.compile(r"\b(19|20)\d{2}\b")


def format_measure(name: str, m: object) -> str:
    """Formata uma medida de desproporcionalidade (PRR/ROR/IC/EBGM)."""
    val = getattr(m, "value", 0.0)
    lo = getattr(m, "ci_lower", 0.0)
    hi = getattr(m, "ci_upper", 0.0)
    sig = "*" if getattr(m, "significant", False) else ""
    return f"- {name}: {val:.2f} (95% CI: {lo:.2f}-{hi:.2f}) {sig}"


def format_strata_table(
    title: str,
    col_name: str,
    strata: list[StratumSignal],
) -> list[str]:
    """Formata tabela markdown de strata (sex, age, country)."""
    items = [s for s in strata if not s.insufficient_data]
    if not items:
        return []
    lines = [
        "",
        f"## {title}",
        f"| Source | {col_name} | Reports | PRR | ROR | Signal |",
        "|--------|-----|---------|-----|-----|--------|",
    ]
    for s in items:
        sig_str = "YES" if s.signal_detected else "NO"
        lines.append(
            f"| {s.source} | {s.stratum_value} | {s.drug_event_count} | "
            f"{s.prr:.2f} | {s.ror:.2f} | {sig_str} |"
        )
    return lines


def format_country_strata_table(strata: list[StratumSignal]) -> list[str]:
    """Formata tabela markdown de cross-country comparison."""
    if not strata:
        return []
    lines = [
        "",
        "## Cross-Country Comparison",
        "| Database | Reports | PRR | Signal |",
        "|----------|---------|-----|--------|",
    ]
    for s in strata:
        prr_str = f"{s.prr:.2f}" if s.prr > 0 else "n/a"
        sig_str = "YES" if s.signal_detected else "NO"
        lines.append(f"| {s.stratum_value} | {s.drug_event_count} | {prr_str} | {sig_str} |")
    return lines


# ---------------------------------------------------------------------------
# Citation formatters
# ---------------------------------------------------------------------------


def _format_authors(authors: list[str]) -> str:
    if not authors:
        return ""

    def _initials(name: str) -> str:
        parts = name.split()
        if len(parts) <= 1:
            return name
        last = parts[0]
        inits = "".join(p[0] for p in parts[1:] if p)
        return f"{last} {inits}"

    if len(authors) == 1:
        return _initials(authors[0])
    if len(authors) == 2:
        return f"{_initials(authors[0])}, {_initials(authors[1])}"
    return f"{_initials(authors[0])}, et al."


def _extract_year(pub_date: str | None) -> str | None:
    if not pub_date:
        return None
    match = _YEAR_RE.search(pub_date)
    return match.group(0) if match else None


def format_citation(article: PubMedArticle) -> str:
    """Formata citação de um artigo — sem bullet prefix.

    Exemplo: Smith J, et al. (2024) Title. *Journal*. PMID:12345678 | DOI:10.x
    """
    parts: list[str] = []

    author_str = _format_authors(article.authors)
    year = _extract_year(article.pub_date)

    if author_str and year:
        parts.append(f"{author_str}. ({year})")
    elif author_str:
        parts.append(f"{author_str}.")
    elif year:
        parts.append(f"({year})")

    parts.append(article.title)

    if article.journal:
        parts.append(f"*{article.journal}*.")

    parts.append(f"PMID:{article.pmid}")

    if article.doi:
        parts.append(f"| DOI:{article.doi}")

    return " ".join(parts)


def format_references(
    articles: list[PubMedArticle],
    *,
    heading: str = "References",
    max_items: int = 0,
    include_abstract: bool = False,
) -> list[str]:
    """Formata seção de referências com heading e citações.

    Args:
        articles: Lista de PubMedArticle.
        heading: Título da seção markdown.
        max_items: Máximo de artigos (0 = todos).
        include_abstract: Incluir snippet do abstract.

    Returns:
        Lista de linhas markdown (vazia se sem artigos).
    """
    if not articles:
        return []

    items = articles[:max_items] if max_items > 0 else articles

    lines: list[str] = ["", f"## {heading}"]
    for art in items:
        lines.append(f"- {format_citation(art)}")
        if include_abstract and art.abstract:
            snippet = art.abstract[:_ABSTRACT_SNIPPET_LEN]
            if len(art.abstract) > _ABSTRACT_SNIPPET_LEN:
                snippet += "..."
            lines.append(f"  > {snippet}")

    return lines
