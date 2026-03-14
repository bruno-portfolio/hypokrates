"""Testes para hypokrates.evidence.models."""

from __future__ import annotations

from datetime import UTC, datetime

from hypokrates.evidence.models import EvidenceBlock, Limitation


class TestLimitation:
    """Testes para enum Limitation."""

    def test_all_values_unique(self) -> None:
        values = [lim.value for lim in Limitation]
        assert len(values) == len(set(values))

    def test_has_expected_members(self) -> None:
        expected = {
            "voluntary_reporting",
            "no_denominator",
            "duplicate_reports",
            "missing_data",
            "indication_bias",
            "notoriety_bias",
            "no_causation",
        }
        actual = {lim.value for lim in Limitation}
        assert expected == actual

    def test_faers_limitations_count(self) -> None:
        """FAERS usa 5 limitações padrão."""
        faers_lims = [
            Limitation.VOLUNTARY_REPORTING,
            Limitation.NO_DENOMINATOR,
            Limitation.DUPLICATE_REPORTS,
            Limitation.MISSING_DATA,
            Limitation.NO_CAUSATION,
        ]
        assert len(faers_lims) == 5


class TestEvidenceBlock:
    """Testes para EvidenceBlock."""

    def _make_block(self, **kwargs: object) -> EvidenceBlock:
        defaults: dict[str, object] = {
            "source": "OpenFDA/FAERS",
            "query": {"drug": "propofol"},
            "retrieved_at": datetime.now(UTC),
            "data": {"events": [{"term": "DEATH", "count": 100}]},
            "limitations": [Limitation.VOLUNTARY_REPORTING],
            "disclaimer": "Test disclaimer.",
        }
        defaults.update(kwargs)
        return EvidenceBlock(**defaults)  # type: ignore[arg-type]

    def test_all_fields_present(self) -> None:
        block = self._make_block(
            source_version="v1",
            methodology="PRR via Rothman-Greenland",
            confidence="signal_detected",
        )
        assert block.source == "OpenFDA/FAERS"
        assert block.source_version == "v1"
        assert block.query == {"drug": "propofol"}
        assert block.retrieved_at is not None
        assert block.data
        assert block.limitations
        assert block.disclaimer
        assert block.methodology
        assert block.confidence

    def test_limitations_are_limitation_enum(self) -> None:
        block = self._make_block(
            limitations=[Limitation.VOLUNTARY_REPORTING, Limitation.NO_CAUSATION]
        )
        for lim in block.limitations:
            assert isinstance(lim, Limitation)

    def test_serialization_roundtrip(self) -> None:
        block = self._make_block()
        data = block.model_dump()
        restored = EvidenceBlock.model_validate(data)
        assert restored.source == block.source
        assert restored.query == block.query
        assert len(restored.limitations) == len(block.limitations)

    def test_disclaimer_not_empty(self) -> None:
        block = self._make_block()
        assert len(block.disclaimer) > 0

    def test_cached_default_false(self) -> None:
        block = self._make_block()
        assert block.cached is False
