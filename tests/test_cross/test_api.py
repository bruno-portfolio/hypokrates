"""Testes para hypokrates.cross.api — mock stats + pubmed."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from unittest.mock import patch

import pytest

from hypokrates.config import configure
from hypokrates.cross.api import hypothesis
from hypokrates.cross.models import HypothesisClassification, HypothesisResult
from hypokrates.models import MetaInfo
from hypokrates.pubmed.models import PubMedArticle, PubMedSearchResult
from hypokrates.stats.models import ContingencyTable, DisproportionalityResult, SignalResult


def _make_signal(*, detected: bool = True, a: int = 100) -> SignalResult:
    """Cria SignalResult mock."""
    return SignalResult(
        drug="propofol",
        event="PRIS",
        table=ContingencyTable(a=a, b=900, c=200, d=8800),
        prr=DisproportionalityResult(
            measure="PRR", value=2.0, ci_lower=1.5, ci_upper=2.5, significant=detected
        ),
        ror=DisproportionalityResult(
            measure="ROR", value=2.2, ci_lower=1.6, ci_upper=3.0, significant=detected
        ),
        ic=DisproportionalityResult(
            measure="IC", value=1.0, ci_lower=0.5, ci_upper=1.5, significant=detected
        ),
        signal_detected=detected,
        meta=MetaInfo(source="OpenFDA/FAERS", retrieved_at=datetime.now(UTC)),
    )


def _make_pubmed_result(
    count: int, articles: list[PubMedArticle] | None = None
) -> PubMedSearchResult:
    """Cria PubMedSearchResult mock."""
    return PubMedSearchResult(
        total_count=count,
        articles=articles or [],
        meta=MetaInfo(source="NCBI/PubMed", retrieved_at=datetime.now(UTC)),
    )


class TestHypothesisAPI:
    """Testes para hypothesis() — cruza sinal + literatura."""

    @pytest.fixture(autouse=True)
    def _disable_cache(self) -> None:
        configure(cache_enabled=False)

    @patch("hypokrates.cross.api.pubmed_api.search_papers")
    @patch("hypokrates.cross.api.stats_api.signal")
    async def test_novel_hypothesis(self, mock_signal: Any, mock_pubmed: Any) -> None:
        """Sinal detectado + 0 papers → novel_hypothesis."""
        mock_signal.return_value = _make_signal(detected=True)
        mock_pubmed.return_value = _make_pubmed_result(0)

        result = await hypothesis("propofol", "PRIS", use_cache=False)
        assert isinstance(result, HypothesisResult)
        assert result.classification == HypothesisClassification.NOVEL_HYPOTHESIS
        assert result.literature_count == 0
        assert "Novel hypothesis" in result.summary

    @patch("hypokrates.cross.api.pubmed_api.search_papers")
    @patch("hypokrates.cross.api.stats_api.signal")
    async def test_emerging_signal(self, mock_signal: Any, mock_pubmed: Any) -> None:
        """Sinal detectado + 3 papers → emerging_signal."""
        articles = [PubMedArticle(pmid=str(i), title=f"Paper {i}") for i in range(3)]
        mock_signal.return_value = _make_signal(detected=True)
        mock_pubmed.return_value = _make_pubmed_result(3, articles)

        result = await hypothesis("propofol", "PRIS", use_cache=False)
        assert result.classification == HypothesisClassification.EMERGING_SIGNAL
        assert result.literature_count == 3
        assert len(result.articles) == 3
        assert "Emerging" in result.summary

    @patch("hypokrates.cross.api.pubmed_api.search_papers")
    @patch("hypokrates.cross.api.stats_api.signal")
    async def test_known_association(self, mock_signal: Any, mock_pubmed: Any) -> None:
        """Sinal detectado + 10 papers → known_association."""
        articles = [PubMedArticle(pmid=str(i), title=f"Paper {i}") for i in range(5)]
        mock_signal.return_value = _make_signal(detected=True)
        mock_pubmed.return_value = _make_pubmed_result(10, articles)

        result = await hypothesis("propofol", "PRIS", use_cache=False)
        assert result.classification == HypothesisClassification.KNOWN_ASSOCIATION
        assert result.literature_count == 10
        assert "Known association" in result.summary

    @patch("hypokrates.cross.api.pubmed_api.search_papers")
    @patch("hypokrates.cross.api.stats_api.signal")
    async def test_no_signal(self, mock_signal: Any, mock_pubmed: Any) -> None:
        """Sem sinal → no_signal independente de papers."""
        mock_signal.return_value = _make_signal(detected=False)
        mock_pubmed.return_value = _make_pubmed_result(50)

        result = await hypothesis("aspirin", "HEADACHE", use_cache=False)
        assert result.classification == HypothesisClassification.NO_SIGNAL
        assert "No signal" in result.summary

    @patch("hypokrates.cross.api.pubmed_api.search_papers")
    @patch("hypokrates.cross.api.stats_api.signal")
    async def test_custom_thresholds(self, mock_signal: Any, mock_pubmed: Any) -> None:
        """Thresholds customizados mudam classificação."""
        mock_signal.return_value = _make_signal(detected=True)
        mock_pubmed.return_value = _make_pubmed_result(3)

        # Default: 3 papers → emerging. Com novel_max=5 → novel.
        result = await hypothesis("propofol", "PRIS", novel_max=5, use_cache=False)
        assert result.classification == HypothesisClassification.NOVEL_HYPOTHESIS
        assert result.thresholds_used["novel_max"] == 5

    @patch("hypokrates.cross.api.pubmed_api.search_papers")
    @patch("hypokrates.cross.api.stats_api.signal")
    async def test_evidence_block_present(self, mock_signal: Any, mock_pubmed: Any) -> None:
        """HypothesisResult tem EvidenceBlock completo."""
        mock_signal.return_value = _make_signal(detected=True)
        mock_pubmed.return_value = _make_pubmed_result(0)

        result = await hypothesis("propofol", "PRIS", use_cache=False)
        assert result.evidence.source == "FAERS+PubMed"
        assert result.evidence.methodology is not None
        assert result.evidence.confidence is not None
        assert len(result.evidence.limitations) > 0

    @patch("hypokrates.cross.api.pubmed_api.search_papers")
    @patch("hypokrates.cross.api.stats_api.signal")
    async def test_thresholds_in_result(self, mock_signal: Any, mock_pubmed: Any) -> None:
        """thresholds_used reflete os valores usados."""
        mock_signal.return_value = _make_signal(detected=True)
        mock_pubmed.return_value = _make_pubmed_result(0)

        result = await hypothesis(
            "propofol", "PRIS", novel_max=2, emerging_max=10, use_cache=False
        )
        assert result.thresholds_used == {"novel_max": 2, "emerging_max": 10}

    @patch("hypokrates.cross.api.pubmed_api.search_papers")
    @patch("hypokrates.cross.api.stats_api.signal")
    async def test_boundary_novel_to_emerging(self, mock_signal: Any, mock_pubmed: Any) -> None:
        """Exatamente novel_max papers → novel. novel_max+1 → emerging."""
        mock_signal.return_value = _make_signal(detected=True)

        # At boundary: 0 papers com novel_max=0 → novel
        mock_pubmed.return_value = _make_pubmed_result(0)
        r1 = await hypothesis("propofol", "PRIS", novel_max=0, use_cache=False)
        assert r1.classification == HypothesisClassification.NOVEL_HYPOTHESIS

        # Just above: 1 paper com novel_max=0 → emerging
        mock_pubmed.return_value = _make_pubmed_result(1)
        r2 = await hypothesis("propofol", "PRIS", novel_max=0, use_cache=False)
        assert r2.classification == HypothesisClassification.EMERGING_SIGNAL

    @patch("hypokrates.cross.api.pubmed_api.search_papers")
    @patch("hypokrates.cross.api.stats_api.signal")
    async def test_boundary_emerging_to_known(self, mock_signal: Any, mock_pubmed: Any) -> None:
        """Exatamente emerging_max papers → emerging. emerging_max+1 → known."""
        mock_signal.return_value = _make_signal(detected=True)

        # At boundary: 5 papers → emerging
        mock_pubmed.return_value = _make_pubmed_result(5)
        r1 = await hypothesis("propofol", "PRIS", emerging_max=5, use_cache=False)
        assert r1.classification == HypothesisClassification.EMERGING_SIGNAL

        # Just above: 6 papers → known
        mock_pubmed.return_value = _make_pubmed_result(6)
        r2 = await hypothesis("propofol", "PRIS", emerging_max=5, use_cache=False)
        assert r2.classification == HypothesisClassification.KNOWN_ASSOCIATION
