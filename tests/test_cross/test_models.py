"""Testes para hypokrates.cross.models — roundtrip e validação."""

from __future__ import annotations

from datetime import UTC, datetime

from hypokrates.cross.models import HypothesisClassification, HypothesisResult
from hypokrates.evidence.models import EvidenceBlock
from hypokrates.models import MetaInfo
from hypokrates.pubmed.models import PubMedArticle
from hypokrates.stats.models import ContingencyTable, DisproportionalityResult, SignalResult


def _make_signal_result(*, signal_detected: bool = True) -> SignalResult:
    """Helper para criar SignalResult de teste."""
    return SignalResult(
        drug="propofol",
        event="PRIS",
        table=ContingencyTable(a=100, b=900, c=200, d=8800),
        prr=DisproportionalityResult(
            measure="PRR", value=2.0, ci_lower=1.5, ci_upper=2.5, significant=True
        ),
        ror=DisproportionalityResult(
            measure="ROR", value=2.2, ci_lower=1.6, ci_upper=3.0, significant=True
        ),
        ic=DisproportionalityResult(
            measure="IC", value=1.0, ci_lower=0.5, ci_upper=1.5, significant=True
        ),
        signal_detected=signal_detected,
        meta=MetaInfo(source="OpenFDA/FAERS", retrieved_at=datetime.now(UTC)),
    )


class TestHypothesisClassification:
    """HypothesisClassification — enum values."""

    def test_values(self) -> None:
        assert HypothesisClassification.NOVEL_HYPOTHESIS == "novel_hypothesis"
        assert HypothesisClassification.EMERGING_SIGNAL == "emerging_signal"
        assert HypothesisClassification.KNOWN_ASSOCIATION == "known_association"
        assert HypothesisClassification.NO_SIGNAL == "no_signal"

    def test_is_str(self) -> None:
        assert isinstance(HypothesisClassification.NOVEL_HYPOTHESIS, str)


class TestHypothesisResult:
    """HypothesisResult — construção e roundtrip."""

    def test_minimal(self) -> None:
        result = HypothesisResult(
            drug="propofol",
            event="PRIS",
            classification=HypothesisClassification.NOVEL_HYPOTHESIS,
            signal=_make_signal_result(),
            literature_count=0,
            evidence=EvidenceBlock(
                source="FAERS+PubMed",
                retrieved_at=datetime.now(UTC),
            ),
            summary="Novel hypothesis: PROPOFOL + PRIS.",
            thresholds_used={"novel_max": 0, "emerging_max": 5},
        )
        assert result.drug == "propofol"
        assert result.classification == HypothesisClassification.NOVEL_HYPOTHESIS
        assert result.literature_count == 0
        assert result.articles == []

    def test_with_articles(self) -> None:
        articles = [PubMedArticle(pmid="111", title="Test")]
        result = HypothesisResult(
            drug="propofol",
            event="PRIS",
            classification=HypothesisClassification.EMERGING_SIGNAL,
            signal=_make_signal_result(),
            literature_count=3,
            articles=articles,
            evidence=EvidenceBlock(
                source="FAERS+PubMed",
                retrieved_at=datetime.now(UTC),
            ),
            summary="Emerging signal.",
            thresholds_used={"novel_max": 0, "emerging_max": 5},
        )
        assert len(result.articles) == 1

    def test_roundtrip(self) -> None:
        result = HypothesisResult(
            drug="propofol",
            event="PRIS",
            classification=HypothesisClassification.KNOWN_ASSOCIATION,
            signal=_make_signal_result(),
            literature_count=10,
            evidence=EvidenceBlock(
                source="FAERS+PubMed",
                retrieved_at=datetime.now(UTC),
            ),
            summary="Known association.",
            thresholds_used={"novel_max": 0, "emerging_max": 5},
        )
        data = result.model_dump()
        restored = HypothesisResult.model_validate(data)
        assert restored.classification == result.classification
        assert restored.literature_count == result.literature_count
