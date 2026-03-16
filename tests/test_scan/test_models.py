"""Testes para hypokrates.scan.models."""

from __future__ import annotations

from datetime import UTC, datetime

from hypokrates.cross.models import HypothesisClassification
from hypokrates.evidence.models import EvidenceBlock
from hypokrates.models import MetaInfo
from hypokrates.scan.models import ScanItem, ScanResult
from hypokrates.stats.models import ContingencyTable, DisproportionalityResult, SignalResult


def _make_signal() -> SignalResult:
    """Cria SignalResult mínimo para testes."""
    table = ContingencyTable(a=100, b=900, c=50, d=9000)
    measure = DisproportionalityResult(
        measure="PRR", value=2.0, ci_lower=1.5, ci_upper=2.5, significant=True
    )
    return SignalResult(
        drug="propofol",
        event="HYPOTENSION",
        table=table,
        prr=measure,
        ror=DisproportionalityResult(
            measure="ROR", value=2.1, ci_lower=1.6, ci_upper=2.7, significant=True
        ),
        ic=DisproportionalityResult(
            measure="IC", value=1.0, ci_lower=0.5, ci_upper=1.5, significant=True
        ),
        ebgm=DisproportionalityResult(
            measure="EBGM", value=2.0, ci_lower=1.5, ci_upper=2.5, significant=True
        ),
        signal_detected=True,
        meta=MetaInfo(source="test", retrieved_at=datetime.now(UTC)),
    )


def _make_evidence() -> EvidenceBlock:
    """Cria EvidenceBlock mínimo para testes."""
    return EvidenceBlock(
        source="test",
        retrieved_at=datetime.now(UTC),
    )


class TestScanItem:
    """Testes para ScanItem."""

    def test_construction(self) -> None:
        item = ScanItem(
            drug="propofol",
            event="HYPOTENSION",
            classification=HypothesisClassification.NOVEL_HYPOTHESIS,
            signal=_make_signal(),
            literature_count=0,
            evidence=_make_evidence(),
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
            signal=_make_signal(),
            literature_count=3,
            evidence=_make_evidence(),
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
