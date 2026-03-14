"""Testes para hypokrates.scan.api."""

from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import AsyncMock, patch

import pytest

from hypokrates.cross.models import HypothesisClassification, HypothesisResult
from hypokrates.evidence.models import EvidenceBlock
from hypokrates.faers.models import FAERSResult
from hypokrates.models import AdverseEvent, MetaInfo
from hypokrates.pubmed.models import PubMedArticle
from hypokrates.scan.api import _score, scan_drug
from hypokrates.stats.models import ContingencyTable, DisproportionalityResult, SignalResult

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_meta() -> MetaInfo:
    return MetaInfo(source="test", retrieved_at=datetime.now(UTC))


def _make_signal(
    *,
    prr_lci: float = 1.5,
    ror_lci: float = 1.6,
    detected: bool = True,
) -> SignalResult:
    return SignalResult(
        drug="propofol",
        event="TEST",
        table=ContingencyTable(a=100, b=900, c=50, d=9000),
        prr=DisproportionalityResult(
            measure="PRR", value=2.0, ci_lower=prr_lci, ci_upper=3.0, significant=detected
        ),
        ror=DisproportionalityResult(
            measure="ROR", value=2.1, ci_lower=ror_lci, ci_upper=3.1, significant=detected
        ),
        ic=DisproportionalityResult(
            measure="IC", value=1.0, ci_lower=0.5, ci_upper=1.5, significant=detected
        ),
        signal_detected=detected,
        meta=_make_meta(),
    )


def _make_evidence() -> EvidenceBlock:
    return EvidenceBlock(source="test", retrieved_at=datetime.now(UTC))


def _make_hypothesis_result(
    event: str,
    classification: HypothesisClassification,
    *,
    signal_detected: bool = True,
    lit_count: int = 0,
    prr_lci: float = 1.5,
    ror_lci: float = 1.6,
) -> HypothesisResult:
    """Factory para HypothesisResult de teste."""
    return HypothesisResult(
        drug="propofol",
        event=event,
        classification=classification,
        signal=_make_signal(prr_lci=prr_lci, ror_lci=ror_lci, detected=signal_detected),
        literature_count=lit_count,
        articles=[PubMedArticle(pmid="123", title="Test")] if lit_count > 0 else [],
        evidence=_make_evidence(),
        summary=f"{classification.value}: propofol + {event}",
        thresholds_used={"novel_max": 0, "emerging_max": 5},
    )


def _make_events(terms: list[str]) -> FAERSResult:
    """Cria FAERSResult com eventos para teste."""
    return FAERSResult(
        events=[AdverseEvent(term=t, count=100 - i) for i, t in enumerate(terms)],
        meta=_make_meta(),
    )


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


@patch("hypokrates.scan.api.cross_api.hypothesis")
@patch("hypokrates.scan.api.faers_api.top_events")
async def test_scan_basic(
    mock_top_events: AsyncMock,
    mock_hypothesis: AsyncMock,
) -> None:
    """3 eventos, classificações mistas → resultado correto."""
    mock_top_events.return_value = _make_events(["NAUSEA", "HEADACHE", "RASH"])

    mock_hypothesis.side_effect = [
        _make_hypothesis_result("NAUSEA", HypothesisClassification.NOVEL_HYPOTHESIS),
        _make_hypothesis_result(
            "HEADACHE",
            HypothesisClassification.KNOWN_ASSOCIATION,
            lit_count=10,
        ),
        _make_hypothesis_result("RASH", HypothesisClassification.EMERGING_SIGNAL, lit_count=3),
    ]

    result = await scan_drug("propofol", top_n=3)

    assert result.drug == "propofol"
    assert result.total_scanned == 3
    assert result.novel_count == 1
    assert result.known_count == 1
    assert result.emerging_count == 1
    assert result.no_signal_count == 0
    assert result.failed_count == 0
    assert len(result.items) == 3


@patch("hypokrates.scan.api.cross_api.hypothesis")
@patch("hypokrates.scan.api.faers_api.top_events")
async def test_scan_scoring_order(
    mock_top_events: AsyncMock,
    mock_hypothesis: AsyncMock,
) -> None:
    """Novel com sinal forte > emerging com sinal fraco."""
    mock_top_events.return_value = _make_events(["A", "B"])

    mock_hypothesis.side_effect = [
        _make_hypothesis_result(
            "A",
            HypothesisClassification.EMERGING_SIGNAL,
            lit_count=3,
            prr_lci=0.5,
            ror_lci=0.6,
        ),
        _make_hypothesis_result(
            "B",
            HypothesisClassification.NOVEL_HYPOTHESIS,
            prr_lci=3.0,
            ror_lci=3.5,
        ),
    ]

    result = await scan_drug("propofol", top_n=2)

    assert result.items[0].event == "B"  # novel com sinal forte
    assert result.items[1].event == "A"  # emerging com sinal fraco
    assert result.items[0].rank == 1
    assert result.items[1].rank == 2
    assert result.items[0].score > result.items[1].score


@patch("hypokrates.scan.api.cross_api.hypothesis")
@patch("hypokrates.scan.api.faers_api.top_events")
async def test_scan_filter_no_signal(
    mock_top_events: AsyncMock,
    mock_hypothesis: AsyncMock,
) -> None:
    """include_no_signal=False filtra corretamente."""
    mock_top_events.return_value = _make_events(["A", "B"])

    mock_hypothesis.side_effect = [
        _make_hypothesis_result(
            "A",
            HypothesisClassification.NOVEL_HYPOTHESIS,
        ),
        _make_hypothesis_result(
            "B",
            HypothesisClassification.NO_SIGNAL,
            signal_detected=False,
        ),
    ]

    result = await scan_drug("propofol", top_n=2, include_no_signal=False)

    assert len(result.items) == 1
    assert result.items[0].event == "A"
    assert result.no_signal_count == 1  # contado mesmo que filtrado


@patch("hypokrates.scan.api.cross_api.hypothesis")
@patch("hypokrates.scan.api.faers_api.top_events")
async def test_scan_include_no_signal(
    mock_top_events: AsyncMock,
    mock_hypothesis: AsyncMock,
) -> None:
    """include_no_signal=True inclui tudo."""
    mock_top_events.return_value = _make_events(["A", "B"])

    mock_hypothesis.side_effect = [
        _make_hypothesis_result("A", HypothesisClassification.NOVEL_HYPOTHESIS),
        _make_hypothesis_result(
            "B",
            HypothesisClassification.NO_SIGNAL,
            signal_detected=False,
        ),
    ]

    result = await scan_drug("propofol", top_n=2, include_no_signal=True)

    assert len(result.items) == 2


@patch("hypokrates.scan.api.cross_api.hypothesis")
@patch("hypokrates.scan.api.faers_api.top_events")
async def test_scan_empty_events(
    mock_top_events: AsyncMock,
    mock_hypothesis: AsyncMock,
) -> None:
    """Droga sem eventos FAERS → ScanResult vazio."""
    mock_top_events.return_value = FAERSResult(events=[], meta=_make_meta())

    result = await scan_drug("unknowndrug", top_n=10)

    assert result.total_scanned == 0
    assert result.items == []
    mock_hypothesis.assert_not_called()


@patch("hypokrates.scan.api.cross_api.hypothesis")
@patch("hypokrates.scan.api.faers_api.top_events")
async def test_scan_partial_failure(
    mock_top_events: AsyncMock,
    mock_hypothesis: AsyncMock,
) -> None:
    """1 de 3 hypothesis falha → 2 items + failed_count=1."""
    mock_top_events.return_value = _make_events(["A", "B", "C"])

    mock_hypothesis.side_effect = [
        _make_hypothesis_result("A", HypothesisClassification.NOVEL_HYPOTHESIS),
        RuntimeError("API error"),
        _make_hypothesis_result("C", HypothesisClassification.EMERGING_SIGNAL, lit_count=2),
    ]

    result = await scan_drug("propofol", top_n=3)

    assert len(result.items) == 2
    assert result.failed_count == 1
    assert "B" in result.skipped_events


@patch("hypokrates.scan.api.cross_api.hypothesis")
@patch("hypokrates.scan.api.faers_api.top_events")
async def test_scan_all_fail(
    mock_top_events: AsyncMock,
    mock_hypothesis: AsyncMock,
) -> None:
    """Todos falham → items vazio, failed_count=N."""
    mock_top_events.return_value = _make_events(["A", "B"])

    mock_hypothesis.side_effect = [
        RuntimeError("error1"),
        RuntimeError("error2"),
    ]

    result = await scan_drug("propofol", top_n=2)

    assert result.items == []
    assert result.failed_count == 2
    assert result.total_scanned == 2


@patch("hypokrates.scan.api.cross_api.hypothesis")
@patch("hypokrates.scan.api.faers_api.top_events")
async def test_scan_ranking(
    mock_top_events: AsyncMock,
    mock_hypothesis: AsyncMock,
) -> None:
    """Ranks atribuídos corretamente (1, 2, 3...)."""
    mock_top_events.return_value = _make_events(["A", "B", "C"])

    mock_hypothesis.side_effect = [
        _make_hypothesis_result(
            "A",
            HypothesisClassification.KNOWN_ASSOCIATION,
            lit_count=10,
            prr_lci=1.0,
            ror_lci=1.0,
        ),
        _make_hypothesis_result(
            "B",
            HypothesisClassification.NOVEL_HYPOTHESIS,
            prr_lci=2.0,
            ror_lci=2.0,
        ),
        _make_hypothesis_result(
            "C",
            HypothesisClassification.EMERGING_SIGNAL,
            lit_count=3,
            prr_lci=1.5,
            ror_lci=1.5,
        ),
    ]

    result = await scan_drug("propofol", top_n=3)

    ranks = [item.rank for item in result.items]
    assert ranks == [1, 2, 3]
    # Verify scores are descending
    scores = [item.score for item in result.items]
    assert scores == sorted(scores, reverse=True)


@patch("hypokrates.scan.api.cross_api.hypothesis")
@patch("hypokrates.scan.api.faers_api.top_events")
async def test_scan_counts(
    mock_top_events: AsyncMock,
    mock_hypothesis: AsyncMock,
) -> None:
    """Contadores de classificação corretos."""
    mock_top_events.return_value = _make_events(["A", "B", "C", "D"])

    mock_hypothesis.side_effect = [
        _make_hypothesis_result("A", HypothesisClassification.NOVEL_HYPOTHESIS),
        _make_hypothesis_result("B", HypothesisClassification.EMERGING_SIGNAL, lit_count=3),
        _make_hypothesis_result("C", HypothesisClassification.KNOWN_ASSOCIATION, lit_count=10),
        _make_hypothesis_result("D", HypothesisClassification.NO_SIGNAL, signal_detected=False),
    ]

    result = await scan_drug("propofol", top_n=4, include_no_signal=True)

    assert result.novel_count == 1
    assert result.emerging_count == 1
    assert result.known_count == 1
    assert result.no_signal_count == 1
    assert result.failed_count == 0


@patch("hypokrates.scan.api.cross_api.hypothesis")
@patch("hypokrates.scan.api.faers_api.top_events")
async def test_scan_on_progress_callback(
    mock_top_events: AsyncMock,
    mock_hypothesis: AsyncMock,
) -> None:
    """Callback on_progress é chamado para cada evento."""
    mock_top_events.return_value = _make_events(["A", "B"])

    mock_hypothesis.side_effect = [
        _make_hypothesis_result("A", HypothesisClassification.NOVEL_HYPOTHESIS),
        _make_hypothesis_result("B", HypothesisClassification.KNOWN_ASSOCIATION, lit_count=10),
    ]

    progress_calls: list[tuple[int, int, str]] = []

    def on_progress(completed: int, total: int, event: str) -> None:
        progress_calls.append((completed, total, event))

    await scan_drug("propofol", top_n=2, on_progress=on_progress)

    assert len(progress_calls) == 2
    # All calls should have total=2
    assert all(t == 2 for _, t, _ in progress_calls)


class TestScore:
    """Testes para _score()."""

    def test_no_signal_score_zero(self) -> None:
        hyp = _make_hypothesis_result(
            "A", HypothesisClassification.NO_SIGNAL, signal_detected=False
        )
        assert _score(hyp) == 0.0

    def test_novel_higher_than_emerging(self) -> None:
        novel = _make_hypothesis_result(
            "A", HypothesisClassification.NOVEL_HYPOTHESIS, prr_lci=1.5, ror_lci=1.5
        )
        emerging = _make_hypothesis_result(
            "B",
            HypothesisClassification.EMERGING_SIGNAL,
            lit_count=3,
            prr_lci=1.5,
            ror_lci=1.5,
        )
        assert _score(novel) > _score(emerging)

    def test_negative_ci_clamped(self) -> None:
        hyp = _make_hypothesis_result(
            "A", HypothesisClassification.NOVEL_HYPOTHESIS, prr_lci=-0.5, ror_lci=-0.3
        )
        score = _score(hyp)
        # base * max(0.0, 0.1) = 10.0 * 0.1 = 1.0
        assert score == pytest.approx(1.0)
