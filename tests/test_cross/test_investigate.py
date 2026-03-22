"""Testes para hypokrates.cross.investigate — mock hypothesis + bulk + canada."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest

from hypokrates.cross.models import (
    HypothesisClassification,
    HypothesisResult,
    InvestigationResult,
    StratumSignal,
)
from hypokrates.evidence.models import EvidenceBlock
from hypokrates.models import MetaInfo
from hypokrates.stats.models import ContingencyTable, DisproportionalityResult, SignalResult


def _make_meta() -> MetaInfo:
    from datetime import UTC, datetime

    return MetaInfo(
        source="test",
        query={},
        total_results=0,
        retrieved_at=datetime.now(UTC),
        disclaimer="test",
    )


def _make_measure(
    name: str = "PRR", value: float = 3.0, sig: bool = True
) -> DisproportionalityResult:
    return DisproportionalityResult(
        measure=name,
        value=value,
        ci_lower=1.5 if sig else 0.5,
        ci_upper=6.0,
        significant=sig,
    )


def _make_signal(
    drug: str = "atorvastatin",
    event: str = "myalgia",
    *,
    a: int = 100,
    prr: float = 3.0,
    detected: bool = True,
) -> SignalResult:
    return SignalResult(
        drug=drug,
        event=event,
        table=ContingencyTable(a=a, b=500, c=200, d=50000),
        prr=_make_measure("PRR", prr, detected),
        ror=_make_measure("ROR", prr * 1.1, detected),
        ic=_make_measure("IC", 1.5, detected),
        ebgm=_make_measure("EBGM", 2.0, detected),
        signal_detected=detected,
        meta=_make_meta(),
    )


def _make_evidence() -> EvidenceBlock:
    from datetime import UTC, datetime

    return EvidenceBlock(
        source="test",
        retrieved_at=datetime.now(UTC),
        confidence="high",
        methodology="test",
        data={},
    )


def _make_hypothesis(
    *,
    canada_reports: int | None = None,
    canada_signal: bool | None = None,
    jader_reports: int | None = None,
    jader_signal: bool | None = None,
) -> HypothesisResult:
    return HypothesisResult(
        drug="atorvastatin",
        event="myalgia",
        classification=HypothesisClassification.KNOWN_ASSOCIATION,
        signal=_make_signal(),
        literature_count=15,
        evidence=_make_evidence(),
        summary="Known association.",
        canada_reports=canada_reports,
        canada_signal=canada_signal,
        jader_reports=jader_reports,
        jader_signal=jader_signal,
    )


def _make_bulk_signal(a: int = 50, prr: float = 2.5, detected: bool = True) -> SignalResult:
    return _make_signal(a=a, prr=prr, detected=detected)


class TestInvestigateResult:
    """Verifica estrutura do InvestigationResult."""

    @patch("hypokrates.cross.investigate._run_canada_strata", new_callable=AsyncMock)
    @patch("hypokrates.cross.investigate._run_faers_strata", new_callable=AsyncMock)
    @patch("hypokrates.cross.investigate.hypothesis", new_callable=AsyncMock)
    async def test_returns_investigation_result(
        self,
        mock_hyp: AsyncMock,
        mock_faers: AsyncMock,
        mock_canada: AsyncMock,
    ) -> None:
        mock_hyp.return_value = _make_hypothesis()
        mock_faers.return_value = []
        mock_canada.return_value = []

        from hypokrates.cross.investigate import investigate

        result = await investigate("atorvastatin", "myalgia")
        assert isinstance(result, InvestigationResult)
        assert result.hypothesis.drug == "atorvastatin"
        assert result.meta.source == "hypokrates/investigate"


class TestSexStrata:
    """Testes de estratificação por sexo."""

    @patch("hypokrates.cross.investigate._run_canada_strata", new_callable=AsyncMock)
    @patch("hypokrates.cross.investigate._run_faers_strata", new_callable=AsyncMock)
    @patch("hypokrates.cross.investigate.hypothesis", new_callable=AsyncMock)
    async def test_sex_strata_from_faers_and_canada(
        self,
        mock_hyp: AsyncMock,
        mock_faers: AsyncMock,
        mock_canada: AsyncMock,
    ) -> None:
        mock_hyp.return_value = _make_hypothesis()
        mock_faers.return_value = [
            StratumSignal(source="FAERS", stratum_type="sex", stratum_value="M", prr=3.5),
            StratumSignal(source="FAERS", stratum_type="sex", stratum_value="F", prr=2.0),
        ]
        mock_canada.return_value = [
            StratumSignal(source="Canada", stratum_type="sex", stratum_value="M", prr=4.0),
            StratumSignal(source="Canada", stratum_type="sex", stratum_value="F", prr=1.5),
        ]

        from hypokrates.cross.investigate import investigate

        result = await investigate("atorvastatin", "myalgia")
        assert len(result.sex_strata) == 4
        faers_sex = [s for s in result.sex_strata if s.source == "FAERS"]
        canada_sex = [s for s in result.sex_strata if s.source == "Canada"]
        assert len(faers_sex) == 2
        assert len(canada_sex) == 2


class TestAgeStrata:
    """Testes de estratificação por faixa etária."""

    @patch("hypokrates.cross.investigate._run_canada_strata", new_callable=AsyncMock)
    @patch("hypokrates.cross.investigate._run_faers_strata", new_callable=AsyncMock)
    @patch("hypokrates.cross.investigate.hypothesis", new_callable=AsyncMock)
    async def test_age_strata_from_faers(
        self,
        mock_hyp: AsyncMock,
        mock_faers: AsyncMock,
        mock_canada: AsyncMock,
    ) -> None:
        mock_hyp.return_value = _make_hypothesis()
        mock_faers.return_value = [
            StratumSignal(source="FAERS", stratum_type="age_group", stratum_value="0-17", prr=1.0),
            StratumSignal(
                source="FAERS", stratum_type="age_group", stratum_value="18-44", prr=2.5
            ),
            StratumSignal(
                source="FAERS", stratum_type="age_group", stratum_value="45-64", prr=3.0
            ),
            StratumSignal(source="FAERS", stratum_type="age_group", stratum_value="65+", prr=5.0),
        ]
        mock_canada.return_value = []

        from hypokrates.cross.investigate import investigate

        result = await investigate("atorvastatin", "myalgia")
        assert len(result.age_strata) == 4
        assert all(s.source == "FAERS" for s in result.age_strata)


class TestCountryStrata:
    """Testes de comparação cross-country."""

    @patch("hypokrates.cross.investigate._run_canada_strata", new_callable=AsyncMock)
    @patch("hypokrates.cross.investigate._run_faers_strata", new_callable=AsyncMock)
    @patch("hypokrates.cross.investigate.hypothesis", new_callable=AsyncMock)
    async def test_country_strata_all_sources(
        self,
        mock_hyp: AsyncMock,
        mock_faers: AsyncMock,
        mock_canada: AsyncMock,
    ) -> None:
        mock_hyp.return_value = _make_hypothesis(
            canada_reports=20, canada_signal=True, jader_reports=10, jader_signal=True
        )
        mock_faers.return_value = []
        mock_canada.return_value = []

        from hypokrates.cross.investigate import investigate

        result = await investigate("atorvastatin", "myalgia")
        assert len(result.country_strata) == 3
        sources = {s.stratum_value for s in result.country_strata}
        assert sources == {"FAERS", "Canada", "JADER"}

    @patch("hypokrates.cross.investigate._run_canada_strata", new_callable=AsyncMock)
    @patch("hypokrates.cross.investigate._run_faers_strata", new_callable=AsyncMock)
    @patch("hypokrates.cross.investigate.hypothesis", new_callable=AsyncMock)
    async def test_country_strata_faers_only(
        self,
        mock_hyp: AsyncMock,
        mock_faers: AsyncMock,
        mock_canada: AsyncMock,
    ) -> None:
        mock_hyp.return_value = _make_hypothesis()
        mock_faers.return_value = []
        mock_canada.return_value = []

        from hypokrates.cross.investigate import investigate

        result = await investigate("atorvastatin", "myalgia")
        assert len(result.country_strata) == 1
        assert result.country_strata[0].stratum_value == "FAERS"


class TestGracefulDegradation:
    """Testes de degradação graceful (bulk/canada indisponíveis)."""

    @patch("hypokrates.cross.investigate._run_canada_strata", new_callable=AsyncMock)
    @patch("hypokrates.cross.investigate._run_faers_strata", new_callable=AsyncMock)
    @patch("hypokrates.cross.investigate.hypothesis", new_callable=AsyncMock)
    async def test_no_bulk_no_canada(
        self,
        mock_hyp: AsyncMock,
        mock_faers: AsyncMock,
        mock_canada: AsyncMock,
    ) -> None:
        mock_hyp.return_value = _make_hypothesis()
        mock_faers.return_value = []
        mock_canada.return_value = []

        from hypokrates.cross.investigate import investigate

        result = await investigate("atorvastatin", "myalgia")
        assert result.sex_strata == []
        assert result.age_strata == []
        assert "Insufficient data" in result.demographic_summary

    @patch("hypokrates.cross.investigate._run_canada_strata", new_callable=AsyncMock)
    @patch("hypokrates.cross.investigate._run_faers_strata", new_callable=AsyncMock)
    @patch("hypokrates.cross.investigate.hypothesis", new_callable=AsyncMock)
    async def test_faers_strata_exception_handled(
        self,
        mock_hyp: AsyncMock,
        mock_faers: AsyncMock,
        mock_canada: AsyncMock,
    ) -> None:
        """Exceção em faers strata não impede resultado."""
        mock_hyp.return_value = _make_hypothesis()
        mock_faers.side_effect = RuntimeError("bulk store unavailable")
        mock_canada.return_value = []

        from hypokrates.cross.investigate import investigate

        result = await investigate("atorvastatin", "myalgia")
        assert isinstance(result, InvestigationResult)
        assert result.sex_strata == []

    @patch("hypokrates.cross.investigate._run_canada_strata", new_callable=AsyncMock)
    @patch("hypokrates.cross.investigate._run_faers_strata", new_callable=AsyncMock)
    @patch("hypokrates.cross.investigate.hypothesis", new_callable=AsyncMock)
    async def test_hypothesis_failure_raises(
        self,
        mock_hyp: AsyncMock,
        mock_faers: AsyncMock,
        mock_canada: AsyncMock,
    ) -> None:
        """hypothesis() é obrigatório — exceção propagada."""
        mock_hyp.side_effect = RuntimeError("network error")
        mock_faers.return_value = []
        mock_canada.return_value = []

        from hypokrates.cross.investigate import investigate

        with pytest.raises(RuntimeError, match="network error"):
            await investigate("atorvastatin", "myalgia")


class TestDemographicSummary:
    """Testes do resumo demográfico."""

    @patch("hypokrates.cross.investigate._run_canada_strata", new_callable=AsyncMock)
    @patch("hypokrates.cross.investigate._run_faers_strata", new_callable=AsyncMock)
    @patch("hypokrates.cross.investigate.hypothesis", new_callable=AsyncMock)
    async def test_sex_notable_difference(
        self,
        mock_hyp: AsyncMock,
        mock_faers: AsyncMock,
        mock_canada: AsyncMock,
    ) -> None:
        mock_hyp.return_value = _make_hypothesis(canada_reports=20, canada_signal=True)
        mock_faers.return_value = [
            StratumSignal(source="FAERS", stratum_type="sex", stratum_value="M", prr=4.5),
            StratumSignal(source="FAERS", stratum_type="sex", stratum_value="F", prr=2.0),
        ]
        mock_canada.return_value = []

        from hypokrates.cross.investigate import investigate

        result = await investigate("atorvastatin", "myalgia")
        assert "notable difference" in result.demographic_summary
        assert "males" in result.demographic_summary

    @patch("hypokrates.cross.investigate._run_canada_strata", new_callable=AsyncMock)
    @patch("hypokrates.cross.investigate._run_faers_strata", new_callable=AsyncMock)
    @patch("hypokrates.cross.investigate.hypothesis", new_callable=AsyncMock)
    async def test_age_notable_difference(
        self,
        mock_hyp: AsyncMock,
        mock_faers: AsyncMock,
        mock_canada: AsyncMock,
    ) -> None:
        mock_hyp.return_value = _make_hypothesis()
        mock_faers.return_value = [
            StratumSignal(source="FAERS", stratum_type="age_group", stratum_value="0-17", prr=1.0),
            StratumSignal(
                source="FAERS", stratum_type="age_group", stratum_value="18-44", prr=2.0
            ),
            StratumSignal(
                source="FAERS", stratum_type="age_group", stratum_value="45-64", prr=2.0
            ),
            StratumSignal(source="FAERS", stratum_type="age_group", stratum_value="65+", prr=8.0),
        ]
        mock_canada.return_value = []

        from hypokrates.cross.investigate import investigate

        result = await investigate("atorvastatin", "myalgia")
        assert "65+" in result.demographic_summary
        assert "Strongest signal" in result.demographic_summary

    @patch("hypokrates.cross.investigate._run_canada_strata", new_callable=AsyncMock)
    @patch("hypokrates.cross.investigate._run_faers_strata", new_callable=AsyncMock)
    @patch("hypokrates.cross.investigate.hypothesis", new_callable=AsyncMock)
    async def test_cross_country_all_confirmed(
        self,
        mock_hyp: AsyncMock,
        mock_faers: AsyncMock,
        mock_canada: AsyncMock,
    ) -> None:
        mock_hyp.return_value = _make_hypothesis(
            canada_reports=20, canada_signal=True, jader_reports=10, jader_signal=True
        )
        mock_faers.return_value = []
        mock_canada.return_value = []

        from hypokrates.cross.investigate import investigate

        result = await investigate("atorvastatin", "myalgia")
        assert "confirmed across all databases" in result.demographic_summary

    @patch("hypokrates.cross.investigate._run_canada_strata", new_callable=AsyncMock)
    @patch("hypokrates.cross.investigate._run_faers_strata", new_callable=AsyncMock)
    @patch("hypokrates.cross.investigate.hypothesis", new_callable=AsyncMock)
    async def test_insufficient_data_strata(
        self,
        mock_hyp: AsyncMock,
        mock_faers: AsyncMock,
        mock_canada: AsyncMock,
    ) -> None:
        """Strata com insufficient_data são filtrados do summary."""
        mock_hyp.return_value = _make_hypothesis()
        mock_faers.return_value = [
            StratumSignal(
                source="FAERS",
                stratum_type="sex",
                stratum_value="M",
                insufficient_data=True,
            ),
            StratumSignal(
                source="FAERS",
                stratum_type="sex",
                stratum_value="F",
                insufficient_data=True,
            ),
        ]
        mock_canada.return_value = []

        from hypokrates.cross.investigate import investigate

        result = await investigate("atorvastatin", "myalgia")
        assert "Insufficient data" in result.demographic_summary
