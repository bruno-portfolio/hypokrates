"""Testes para hypokrates.pubmed.models — roundtrip e validação."""

from __future__ import annotations

from datetime import UTC, datetime

from hypokrates.models import MetaInfo
from hypokrates.pubmed.models import PubMedArticle, PubMedSearchResult


class TestPubMedArticle:
    """PubMedArticle — construção e serialização."""

    def test_minimal_article(self) -> None:
        article = PubMedArticle(pmid="12345", title="Test article")
        assert article.pmid == "12345"
        assert article.title == "Test article"
        assert article.authors == []
        assert article.journal is None
        assert article.doi is None

    def test_full_article(self) -> None:
        article = PubMedArticle(
            pmid="99999",
            title="Full article",
            authors=["Author A", "Author B"],
            journal="Test Journal",
            pub_date="2024 Jan",
            doi="10.1234/test",
        )
        assert len(article.authors) == 2
        assert article.journal == "Test Journal"
        assert article.doi == "10.1234/test"

    def test_roundtrip(self) -> None:
        article = PubMedArticle(
            pmid="12345",
            title="Test",
            authors=["A"],
            journal="J",
            pub_date="2024",
            doi="10.0/x",
        )
        data = article.model_dump()
        restored = PubMedArticle.model_validate(data)
        assert restored == article


class TestPubMedSearchResult:
    """PubMedSearchResult — construção e roundtrip."""

    def test_empty_result(self) -> None:
        result = PubMedSearchResult(
            meta=MetaInfo(source="NCBI/PubMed", retrieved_at=datetime.now(UTC))
        )
        assert result.total_count == 0
        assert result.articles == []
        assert result.query_translation is None

    def test_with_articles(self) -> None:
        articles = [
            PubMedArticle(pmid="1", title="A"),
            PubMedArticle(pmid="2", title="B"),
        ]
        result = PubMedSearchResult(
            total_count=100,
            articles=articles,
            query_translation="test query",
            meta=MetaInfo(source="NCBI/PubMed", retrieved_at=datetime.now(UTC)),
        )
        assert result.total_count == 100
        assert len(result.articles) == 2
        assert result.query_translation == "test query"

    def test_roundtrip(self) -> None:
        result = PubMedSearchResult(
            total_count=5,
            articles=[PubMedArticle(pmid="1", title="X")],
            meta=MetaInfo(source="NCBI/PubMed", retrieved_at=datetime.now(UTC)),
        )
        data = result.model_dump()
        restored = PubMedSearchResult.model_validate(data)
        assert restored.total_count == result.total_count
        assert len(restored.articles) == 1
