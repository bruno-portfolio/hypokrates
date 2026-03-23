"""Classificação de artigos PubMed por tipo de estudo."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from hypokrates.pubmed.models import PubMedArticle

_PATTERNS: dict[str, list[str]] = {
    "review": [
        "systematic review",
        "meta-analysis",
        "meta analysis",
        "scoping review",
        "cochrane",
    ],
    "case_report": [
        "case report",
        "case series",
        "we report a case",
        "we present a case",
    ],
    "mechanism": [
        "mechanism",
        "pathway",
        "receptor",
        "pharmacodynamic",
        "in vitro",
        "preclinical",
    ],
    "epidemiology": [
        "cohort",
        "retrospective",
        "population-based",
        "pharmacovigilance",
        "disproportionality",
        "database study",
        "faers",
    ],
    "clinical": [
        "randomized",
        "randomised",
        "clinical trial",
        "phase ii",
        "phase iii",
        "double-blind",
        "placebo-controlled",
    ],
}


def classify_article(article: PubMedArticle) -> str:
    """Classifica artigo por tipo de estudo via keyword matching."""
    text = ((article.title or "") + " " + (article.abstract or "")).lower()
    for category, keywords in _PATTERNS.items():
        if any(kw in text for kw in keywords):
            return category
    return ""
