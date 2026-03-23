"""Testes para hypokrates.scan.models."""

from __future__ import annotations

from datetime import UTC, datetime

from hypokrates.cross.models import HypothesisClassification
from hypokrates.models import MetaInfo
from hypokrates.scan.models import ScanItem, ScanResult
from tests.helpers import make_evidence, make_signal


class TestScanItem:
    """Testes para ScanItem."""

    def test_construction(self) -> None:
        item = ScanItem(
            drug="propofol",
            event="HYPOTENSION",
            classification=HypothesisClassification.NOVEL_HYPOTHESIS,
            signal=make_signal(event="HYPOTENSION"),
            literature_count=0,
            evidence=make_evidence(),
            summary="Novel hypothesis: PROPOFOL + HYPOTENSION.",
            score=15.0,
            rank=1,
        )
        assert item.drug == "propofol"
        assert item.event == "HYPOTENSION"
        assert item.classification == HypothesisClassification.NOVEL_HYPOTHESIS
        assert item.score == 15.0
        assert item.rank == 1
        assert item.literature_count == 0
        assert item.articles == []

    def test_roundtrip(self) -> None:
        item = ScanItem(
            drug="propofol",
            event="HYPOTENSION",
            classification=HypothesisClassification.EMERGING_SIGNAL,
            signal=make_signal(event="HYPOTENSION"),
            literature_count=3,
            evidence=make_evidence(),
            summary="test",
            score=7.5,
            rank=2,
        )
        data = item.model_dump()
        restored = ScanItem.model_validate(data)
        assert restored.drug == item.drug
        assert restored.score == item.score
        assert restored.classification == item.classification


class TestScanResult:
    """Testes para ScanResult."""

    def test_construction(self) -> None:
        result = ScanResult(
            drug="propofol",
            total_scanned=20,
            novel_count=2,
            emerging_count=5,
            known_count=3,
            no_signal_count=10,
            meta=MetaInfo(source="test", retrieved_at=datetime.now(UTC)),
        )
        assert result.drug == "propofol"
        assert result.total_scanned == 20
        assert result.novel_count == 2
        assert result.items == []
        assert result.failed_count == 0
        assert result.skipped_events == []

    def test_roundtrip(self) -> None:
        result = ScanResult(
            drug="propofol",
            total_scanned=10,
            novel_count=1,
            emerging_count=2,
            known_count=3,
            no_signal_count=4,
            failed_count=1,
            skipped_events=["NAUSEA"],
            meta=MetaInfo(source="test", retrieved_at=datetime.now(UTC)),
        )
        data = result.model_dump()
        restored = ScanResult.model_validate(data)
        assert restored.total_scanned == result.total_scanned
        assert restored.failed_count == 1
        assert restored.skipped_events == ["NAUSEA"]

    def test_counters(self) -> None:
        result = ScanResult(
            drug="propofol",
            total_scanned=15,
            novel_count=3,
            emerging_count=4,
            known_count=2,
            no_signal_count=5,
            failed_count=1,
            meta=MetaInfo(source="test", retrieved_at=datetime.now(UTC)),
        )
        total_classified = (
            result.novel_count
            + result.emerging_count
            + result.known_count
            + result.no_signal_count
            + result.failed_count
        )
        assert total_classified == result.total_scanned
