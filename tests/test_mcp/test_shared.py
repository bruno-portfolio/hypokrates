"""Testes para hypokrates.mcp.tools._shared — citation formatters."""

from __future__ import annotations

from hypokrates.mcp.tools._shared import (
    _extract_year,
    _format_authors,
    format_categorized_references,
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


class TestCategorizedReferences:
    """Testes para format_categorized_references()."""

    def test_empty(self) -> None:
        assert format_categorized_references([]) == []

    def test_groups_by_category(self) -> None:
        articles = [
            PubMedArticle(pmid="1", title="Review article", category="review"),
            PubMedArticle(pmid="2", title="Cohort study", category="epidemiology"),
            PubMedArticle(pmid="3", title="Case report", category="case_report"),
        ]
        result = "\n".join(format_categorized_references(articles))
        assert "Reviews & Meta-analyses" in result
        assert "Epidemiology & Pharmacovigilance" in result
        assert "Case Reports" in result

    def test_respects_category_order(self) -> None:
        articles = [
            PubMedArticle(pmid="1", title="Case report", category="case_report"),
            PubMedArticle(pmid="2", title="Review", category="review"),
        ]
        result = "\n".join(format_categorized_references(articles))
        review_pos = result.index("Reviews & Meta-analyses")
        case_pos = result.index("Case Reports")
        assert review_pos < case_pos

    def test_max_per_category(self) -> None:
        articles = [
            PubMedArticle(pmid=str(i), title=f"Review {i}", category="review") for i in range(5)
        ]
        result = "\n".join(format_categorized_references(articles, max_per_category=2))
        assert "Review 0" in result
        assert "Review 1" in result
        assert "Review 2" not in result

    def test_uncategorized_in_other(self) -> None:
        articles = [
            PubMedArticle(pmid="1", title="Generic article", category=""),
        ]
        result = "\n".join(format_categorized_references(articles))
        assert "Other" in result

    def test_includes_abstract_snippet(self) -> None:
        articles = [
            PubMedArticle(
                pmid="1",
                title="Test",
                category="review",
                abstract="This is a test abstract.",
            ),
        ]
        result = "\n".join(format_categorized_references(articles, include_abstract=True))
        assert "> This is a test abstract" in result
