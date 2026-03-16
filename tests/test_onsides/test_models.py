"""Testes para onsides/models.py."""

from __future__ import annotations

from datetime import UTC, datetime

from hypokrates.models import MetaInfo
from hypokrates.onsides.models import OnSIDESEvent, OnSIDESResult


class TestOnSIDESModels:
    """Testes dos modelos Pydantic."""

    def test_onsides_event(self) -> None:
        ev = OnSIDESEvent(
            meddra_id=10006093,
            meddra_name="Bradycardia",
            label_section="AR",
            confidence=0.92,
            sources=["US", "EU", "UK"],
            num_sources=3,
        )
        assert ev.meddra_id == 10006093
        assert ev.meddra_name == "Bradycardia"
        assert ev.label_section == "AR"
        assert ev.confidence == 0.92
        assert len(ev.sources) == 3
        assert ev.num_sources == 3

    def test_onsides_event_defaults(self) -> None:
        ev = OnSIDESEvent(
            meddra_id=1,
            meddra_name="Test",
            label_section="AR",
            confidence=0.5,
        )
        assert ev.sources == []
        assert ev.num_sources == 0

    def test_onsides_result(self) -> None:
        result = OnSIDESResult(
            drug_name="propofol",
            events=[
                OnSIDESEvent(
                    meddra_id=10006093,
                    meddra_name="Bradycardia",
                    label_section="AR",
                    confidence=0.92,
                    sources=["US"],
                    num_sources=1,
                )
            ],
            total_events=1,
            meta=MetaInfo(
                source="OnSIDES",
                query={"drug": "propofol"},
                total_results=1,
                retrieved_at=datetime.now(UTC),
            ),
        )
        assert result.drug_name == "propofol"
        assert len(result.events) == 1
        assert result.total_events == 1

    def test_onsides_result_empty(self) -> None:
        result = OnSIDESResult(
            drug_name="unknown",
            meta=MetaInfo(
                source="OnSIDES",
                query={"drug": "unknown"},
                total_results=0,
                retrieved_at=datetime.now(UTC),
            ),
        )
        assert result.events == []
        assert result.total_events == 0
