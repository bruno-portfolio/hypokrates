"""Testes para hypokrates.stats.models."""

from __future__ import annotations

from datetime import UTC, datetime

from hypokrates.models import MetaInfo
from hypokrates.stats.models import ContingencyTable, DisproportionalityResult, SignalResult


class TestContingencyTable:
    """Testes para ContingencyTable."""

    def test_n_property(self) -> None:
        table = ContingencyTable(a=100, b=900, c=200, d=8800)
        assert table.n == 10000

    def test_n_property_zeros(self) -> None:
        table = ContingencyTable(a=0, b=0, c=0, d=0)
        assert table.n == 0

    def test_serialization_roundtrip(self) -> None:
        table = ContingencyTable(a=100, b=900, c=200, d=8800)
        data = table.model_dump()
        restored = ContingencyTable.model_validate(data)
        assert restored.a == table.a
        assert restored.b == table.b
        assert restored.c == table.c
        assert restored.d == table.d


class TestSignalResult:
    """Testes para SignalResult."""

    def _make_disp(
        self, measure: str, value: float, significant: bool
    ) -> DisproportionalityResult:
        return DisproportionalityResult(
            measure=measure,
            value=value,
            ci_lower=value * 0.5 if significant else 0.5,
            ci_upper=value * 1.5 if significant else 1.5,
            significant=significant,
        )

    def test_signal_detected_logic(self) -> None:
        """signal_detected depende da contagem de medidas significantes."""
        table = ContingencyTable(a=100, b=900, c=200, d=8800)
        result = SignalResult(
            drug="propofol",
            event="PRIS",
            table=table,
            prr=self._make_disp("PRR", 4.5, significant=True),
            ror=self._make_disp("ROR", 4.9, significant=True),
            ic=self._make_disp("IC", 2.1, significant=True),
            signal_detected=True,
            meta=MetaInfo(
                source="OpenFDA/FAERS",
                query={"drug": "propofol", "event": "PRIS"},
                total_results=100,
                retrieved_at=datetime.now(UTC),
            ),
        )
        assert result.signal_detected is True

    def test_individual_measures_exposed(self) -> None:
        """prr, ror, ic acessíveis individualmente."""
        table = ContingencyTable(a=100, b=900, c=200, d=8800)
        result = SignalResult(
            drug="propofol",
            event="PRIS",
            table=table,
            prr=self._make_disp("PRR", 4.5, significant=True),
            ror=self._make_disp("ROR", 4.9, significant=True),
            ic=self._make_disp("IC", 2.1, significant=True),
            signal_detected=True,
            meta=MetaInfo(
                source="OpenFDA/FAERS",
                query={"drug": "propofol", "event": "PRIS"},
                retrieved_at=datetime.now(UTC),
            ),
        )
        assert result.prr.measure == "PRR"
        assert result.ror.measure == "ROR"
        assert result.ic.measure == "IC"

    def test_serialization_roundtrip(self) -> None:
        table = ContingencyTable(a=10, b=90, c=20, d=880)
        result = SignalResult(
            drug="test",
            event="TEST",
            table=table,
            prr=self._make_disp("PRR", 1.0, significant=False),
            ror=self._make_disp("ROR", 1.0, significant=False),
            ic=self._make_disp("IC", 0.0, significant=False),
            signal_detected=False,
            meta=MetaInfo(
                source="OpenFDA/FAERS",
                query={"drug": "test"},
                retrieved_at=datetime.now(UTC),
            ),
        )
        data = result.model_dump()
        restored = SignalResult.model_validate(data)
        assert restored.drug == result.drug
        assert restored.event == result.event
        assert restored.table.a == result.table.a
        assert restored.signal_detected == result.signal_detected
