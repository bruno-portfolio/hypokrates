"""Testes para opentargets/api.py — API pública."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import AsyncMock, patch

from hypokrates.opentargets.api import drug_adverse_events, drug_safety_score
from hypokrates.opentargets.models import OTDrugSafety

GOLDEN = Path(__file__).parent.parent / "golden_data" / "opentargets"


def _load_golden(name: str) -> dict[str, object]:
    return json.loads((GOLDEN / name).read_text())  # type: ignore[return-value]


class TestDrugAdverseEvents:
    """Testes para drug_adverse_events()."""

    async def test_found(self) -> None:
        search_data = _load_golden("search_propofol.json")["data"]
        ae_data = _load_golden("adverse_events_propofol.json")["data"]

        with patch("hypokrates.opentargets.api.OpenTargetsClient") as mock_client_cls:
            instance = AsyncMock()
            instance.query.side_effect = [search_data, ae_data]
            instance.close = AsyncMock()
            mock_client_cls.return_value = instance

            result = await drug_adverse_events("propofol", use_cache=False)

        assert result.chembl_id == "CHEMBL526"
        assert result.total_count == 150
        assert len(result.adverse_events) == 5
        assert result.critical_value == 3.84

    async def test_drug_not_found(self) -> None:
        with patch("hypokrates.opentargets.api.OpenTargetsClient") as mock_client_cls:
            instance = AsyncMock()
            instance.query.return_value = {"search": {"hits": []}}
            instance.close = AsyncMock()
            mock_client_cls.return_value = instance

            result = await drug_adverse_events("nonexistent", use_cache=False)

        assert result.chembl_id == ""
        assert result.total_count == 0

    async def test_meta_source(self) -> None:
        search_data = _load_golden("search_propofol.json")["data"]
        ae_data = _load_golden("adverse_events_propofol.json")["data"]

        with patch("hypokrates.opentargets.api.OpenTargetsClient") as mock_client_cls:
            instance = AsyncMock()
            instance.query.side_effect = [search_data, ae_data]
            instance.close = AsyncMock()
            mock_client_cls.return_value = instance

            result = await drug_adverse_events("propofol", use_cache=False)

        assert result.meta.source == "OpenTargets"


class TestDrugSafetyScore:
    """Testes para drug_safety_score()."""

    async def test_found_with_cache(self) -> None:
        from datetime import UTC, datetime

        from hypokrates.models import MetaInfo
        from hypokrates.opentargets.models import OTAdverseEvent

        cache = OTDrugSafety(
            drug_name="propofol",
            chembl_id="CHEMBL526",
            adverse_events=[
                OTAdverseEvent(name="Bradycardia", count=980, log_lr=18.72),
                OTAdverseEvent(name="Hypotension", count=2100, log_lr=15.31),
            ],
            meta=MetaInfo(source="test", retrieved_at=datetime.now(UTC)),
        )

        score = await drug_safety_score("propofol", "bradycardia", _safety_cache=cache)
        assert score == 18.72

    async def test_not_found_in_cache(self) -> None:
        from datetime import UTC, datetime

        from hypokrates.models import MetaInfo

        cache = OTDrugSafety(
            drug_name="propofol",
            chembl_id="CHEMBL526",
            adverse_events=[],
            meta=MetaInfo(source="test", retrieved_at=datetime.now(UTC)),
        )

        score = await drug_safety_score("propofol", "unknown_event", _safety_cache=cache)
        assert score is None

    async def test_case_insensitive_match(self) -> None:
        from datetime import UTC, datetime

        from hypokrates.models import MetaInfo
        from hypokrates.opentargets.models import OTAdverseEvent

        cache = OTDrugSafety(
            drug_name="propofol",
            chembl_id="CHEMBL526",
            adverse_events=[
                OTAdverseEvent(name="BRADYCARDIA", count=980, log_lr=18.72),
            ],
            meta=MetaInfo(source="test", retrieved_at=datetime.now(UTC)),
        )

        score = await drug_safety_score("propofol", "bradycardia", _safety_cache=cache)
        assert score == 18.72

    async def test_without_cache_calls_api(self) -> None:
        search_data = _load_golden("search_propofol.json")["data"]
        ae_data = _load_golden("adverse_events_propofol.json")["data"]

        with patch("hypokrates.opentargets.api.OpenTargetsClient") as mock_client_cls:
            instance = AsyncMock()
            instance.query.side_effect = [search_data, ae_data]
            instance.close = AsyncMock()
            mock_client_cls.return_value = instance

            score = await drug_safety_score("propofol", "Bradycardia", use_cache=False)

        assert score == 18.72

    async def test_event_not_in_results(self) -> None:
        search_data = _load_golden("search_propofol.json")["data"]
        ae_data = _load_golden("adverse_events_propofol.json")["data"]

        with patch("hypokrates.opentargets.api.OpenTargetsClient") as mock_client_cls:
            instance = AsyncMock()
            instance.query.side_effect = [search_data, ae_data]
            instance.close = AsyncMock()
            mock_client_cls.return_value = instance

            score = await drug_safety_score("propofol", "nonexistent_event", use_cache=False)

        assert score is None
