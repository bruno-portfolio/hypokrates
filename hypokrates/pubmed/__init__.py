"""PubMed module — busca de literatura via NCBI E-utilities."""

from hypokrates.pubmed.api import count_papers, search_papers
from hypokrates.pubmed.models import PubMedArticle, PubMedSearchResult

__all__ = [
    "PubMedArticle",
    "PubMedSearchResult",
    "count_papers",
    "search_papers",
]
