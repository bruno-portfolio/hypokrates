"""Testes para hypokrates.mcp.tools._shared — citation formatters."""

from __future__ import annotations

from hypokrates.mcp.tools._shared import (
    _extract_year,
    _format_authors,
    format_citation,
    format_references,
)
from hypokrates.pubmed.models import PubMedArticle


class TestSharedFormatters:
    """Testes para _shared.py — citation formatters."""

    def test_format_citation_full(self) -> None:
        art = PubMedArticle(
            pmid="12345678",
            title="Drug safety review",
            authors=["Smith John", "Jones Mary"],
            journal="Clinical Pharmacology",
            pub_date="2024 Jan",
            doi="10.1234/test",
        )
        result = format_citation(art)
        assert "Smith J, Jones M" in result
        assert "(2024)" in result
        assert "Drug safety review" in result
        assert "*Clinical Pharmacology*" in result
        assert "PMID:12345678" in result
        assert "DOI:10.1234/test" in result

    def test_format_citation_minimal(self) -> None:
        art = PubMedArticle(pmid="111", title="Minimal article")
        result = format_citation(art)
        assert "Minimal article" in result
        assert "PMID:111" in result
        assert "DOI:" not in result
        assert "*" not in result

    def test_format_citation_three_authors_et_al(self) -> None:
        art = PubMedArticle(
            pmid="222",
            title="Multi-author study",
            authors=["Smith John", "Jones Mary", "Brown Alice"],
            pub_date="2023",
        )
        result = format_citation(art)
        assert "Smith J, et al." in result
        assert "Jones" not in result
        assert "(2023)" in result

    def test_format_references_empty(self) -> None:
        assert format_references([]) == []

    def test_format_references_max_items(self) -> None:
        articles = [PubMedArticle(pmid=str(i), title=f"Article {i}") for i in range(5)]
        result = format_references(articles, max_items=2)
        content = "\n".join(result)
        assert "Article 0" in content
        assert "Article 1" in content
        assert "Article 2" not in content

    def test_format_references_with_abstract(self) -> None:
        art = PubMedArticle(
            pmid="333",
            title="Abstract test",
            abstract="This is a test abstract with enough content to verify.",
        )
        result = format_references([art], include_abstract=True)
        content = "\n".join(result)
        assert "Abstract test" in content
        assert "> This is a test abstract" in content

    def test_extract_year_formats(self) -> None:
        assert _extract_year("2024 Jan") == "2024"
        assert _extract_year("2024") == "2024"
        assert _extract_year("Jan-Feb 2023") == "2023"
        assert _extract_year(None) is None
        assert _extract_year("") is None
        assert _extract_year("no year here") is None

    def test_format_authors_single(self) -> None:
        assert _format_authors(["Smith John"]) == "Smith J"
        assert _format_authors([]) == ""

    def test_format_authors_two(self) -> None:
        result = _format_authors(["Smith John", "Jones Mary"])
        assert result == "Smith J, Jones M"
