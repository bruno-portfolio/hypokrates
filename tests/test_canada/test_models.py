"""Testes para canada/models.py."""

from __future__ import annotations

from datetime import UTC, datetime

from hypokrates.canada.models import CanadaBulkStatus, CanadaSignalResult
from hypokrates.models import MetaInfo


class TestCanadaModels:
    """Testes dos modelos Pydantic."""

    def test_signal_result(self) -> None:
        result = CanadaSignalResult(
            drug="PROPOFOL",
            event="Bradycardia",
            drug_event_count=5,
            drug_total=100,
            event_total=50,
            total_reports=10000,
            prr=3.5,
            signal_detected=True,
            meta=MetaInfo(
                source="Canada Vigilance",
                query={"drug": "PROPOFOL"},
                total_results=5,
                retrieved_at=datetime.now(UTC),
            ),
        )
        assert result.drug == "PROPOFOL"
        assert result.prr == 3.5
        assert result.signal_detected is True

    def test_signal_result_defaults(self) -> None:
        result = CanadaSignalResult(
            drug="test",
            event="test",
            meta=MetaInfo(
                source="Canada Vigilance",
                query={},
                total_results=0,
                retrieved_at=datetime.now(UTC),
            ),
        )
        assert result.drug_event_count == 0
        assert result.prr == 0.0
        assert result.signal_detected is False

    def test_bulk_status(self) -> None:
        status = CanadaBulkStatus(
            loaded=True,
            total_reports=738000,
            total_drugs=1500000,
            total_reactions=1200000,
            date_range="1965-01-01 to 2025-12-31",
            meta=MetaInfo(
                source="Canada Vigilance",
                query={"action": "status"},
                total_results=738000,
                retrieved_at=datetime.now(UTC),
            ),
        )
        assert status.loaded is True
        assert status.total_reports == 738000
