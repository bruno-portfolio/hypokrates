"""Testes para hypokrates.cross.investigate — mock hypothesis + bulk + canada."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest

from hypokrates.cross.models import (
    CoAdminAnalysis,
    HypothesisClassification,
    HypothesisResult,
    InvestigationResult,
    StratumSignal,
)
from hypokrates.faers.models import CoSuspectProfile
from hypokrates.stats.models import SignalResult
from tests.helpers import make_evidence, make_signal


def _make_hypothesis(
    *,
    a: int = 100,
    prr: float = 3.0,
    canada_reports: int | None = None,
    canada_signal: bool | None = None,
    jader_reports: int | None = None,
    jader_signal: bool | None = None,
    indication_confounding: bool = False,
    coadmin: CoAdminAnalysis | None = None,
) -> HypothesisResult:
    return HypothesisResult(
        drug="atorvastatin",
        event="myalgia",
        classification=HypothesisClassification.KNOWN_ASSOCIATION,
        signal=make_signal(drug="atorvastatin", event="myalgia", a=a, prr=prr),
        literature_count=15,
        evidence=make_evidence(confidence="high", methodology="test"),
        summary="Known association.",
        canada_reports=canada_reports,
        canada_signal=canada_signal,
        jader_reports=jader_reports,
        jader_signal=jader_signal,
        indication_confounding=indication_confounding,
        coadmin=coadmin,
    )


def _make_bulk_signal(a: int = 50, prr: float = 2.5, detected: bool = True) -> SignalResult:
    return make_signal(drug="atorvastatin", event="myalgia", a=a, prr=prr, detected=detected)


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


class TestCaveats:
    """Testes de caveats automáticos."""

    @patch("hypokrates.cross.investigate._run_canada_strata", new_callable=AsyncMock)
    @patch("hypokrates.cross.investigate._run_faers_strata", new_callable=AsyncMock)
    @patch("hypokrates.cross.investigate.hypothesis", new_callable=AsyncMock)
    async def test_low_count(
        self,
        mock_hyp: AsyncMock,
        mock_faers: AsyncMock,
        mock_canada: AsyncMock,
    ) -> None:
        mock_hyp.return_value = _make_hypothesis(a=3)
        mock_faers.return_value = []
        mock_canada.return_value = []

        from hypokrates.cross.investigate import investigate

        result = await investigate("atorvastatin", "myalgia")
        assert any("LOW COUNT" in c for c in result.caveats)

    @patch("hypokrates.cross.investigate._run_canada_strata", new_callable=AsyncMock)
    @patch("hypokrates.cross.investigate._run_faers_strata", new_callable=AsyncMock)
    @patch("hypokrates.cross.investigate.hypothesis", new_callable=AsyncMock)
    async def test_non_replication(
        self,
        mock_hyp: AsyncMock,
        mock_faers: AsyncMock,
        mock_canada: AsyncMock,
    ) -> None:
        mock_hyp.return_value = _make_hypothesis(
            canada_reports=2,
            canada_signal=False,
            jader_reports=0,
            jader_signal=False,
        )
        mock_faers.return_value = []
        mock_canada.return_value = []

        from hypokrates.cross.investigate import investigate

        result = await investigate("atorvastatin", "myalgia")
        assert any("NON-REPLICATION" in c for c in result.caveats)

    @patch("hypokrates.cross.investigate._run_canada_strata", new_callable=AsyncMock)
    @patch("hypokrates.cross.investigate._run_faers_strata", new_callable=AsyncMock)
    @patch("hypokrates.cross.investigate.hypothesis", new_callable=AsyncMock)
    async def test_sex_concentration(
        self,
        mock_hyp: AsyncMock,
        mock_faers: AsyncMock,
        mock_canada: AsyncMock,
    ) -> None:
        mock_hyp.return_value = _make_hypothesis()
        mock_faers.return_value = [
            StratumSignal(
                source="FAERS",
                stratum_type="sex",
                stratum_value="F",
                drug_event_count=90,
                prr=4.0,
            ),
            StratumSignal(
                source="FAERS",
                stratum_type="sex",
                stratum_value="M",
                drug_event_count=10,
                prr=2.0,
            ),
        ]
        mock_canada.return_value = []

        from hypokrates.cross.investigate import investigate

        result = await investigate("atorvastatin", "myalgia")
        assert any("SEX CONCENTRATION" in c for c in result.caveats)

    @patch("hypokrates.cross.investigate._run_canada_strata", new_callable=AsyncMock)
    @patch("hypokrates.cross.investigate._run_faers_strata", new_callable=AsyncMock)
    @patch("hypokrates.cross.investigate.hypothesis", new_callable=AsyncMock)
    async def test_age_concentration(
        self,
        mock_hyp: AsyncMock,
        mock_faers: AsyncMock,
        mock_canada: AsyncMock,
    ) -> None:
        mock_hyp.return_value = _make_hypothesis()
        mock_faers.return_value = [
            StratumSignal(
                source="FAERS",
                stratum_type="age_group",
                stratum_value="0-17",
                drug_event_count=5,
                prr=1.0,
            ),
            StratumSignal(
                source="FAERS",
                stratum_type="age_group",
                stratum_value="18-44",
                drug_event_count=5,
                prr=2.0,
            ),
            StratumSignal(
                source="FAERS",
                stratum_type="age_group",
                stratum_value="45-64",
                drug_event_count=80,
                prr=8.0,
            ),
            StratumSignal(
                source="FAERS",
                stratum_type="age_group",
                stratum_value="65+",
                drug_event_count=5,
                prr=2.0,
            ),
        ]
        mock_canada.return_value = []

        from hypokrates.cross.investigate import investigate

        result = await investigate("atorvastatin", "myalgia")
        assert any("AGE CONCENTRATION" in c for c in result.caveats)

    @patch("hypokrates.cross.investigate._run_canada_strata", new_callable=AsyncMock)
    @patch("hypokrates.cross.investigate._run_faers_strata", new_callable=AsyncMock)
    @patch("hypokrates.cross.investigate.hypothesis", new_callable=AsyncMock)
    async def test_prr_inflation(
        self,
        mock_hyp: AsyncMock,
        mock_faers: AsyncMock,
        mock_canada: AsyncMock,
    ) -> None:
        mock_hyp.return_value = _make_hypothesis(prr=3.0)
        mock_faers.return_value = [
            StratumSignal(
                source="FAERS",
                stratum_type="sex",
                stratum_value="F",
                drug_event_count=50,
                prr=12.0,
            ),
            StratumSignal(
                source="FAERS",
                stratum_type="sex",
                stratum_value="M",
                drug_event_count=50,
                prr=2.0,
            ),
        ]
        mock_canada.return_value = []

        from hypokrates.cross.investigate import investigate

        result = await investigate("atorvastatin", "myalgia")
        assert any("PRR INFLATION" in c for c in result.caveats)

    @patch("hypokrates.cross.investigate._run_canada_strata", new_callable=AsyncMock)
    @patch("hypokrates.cross.investigate._run_faers_strata", new_callable=AsyncMock)
    @patch("hypokrates.cross.investigate.hypothesis", new_callable=AsyncMock)
    async def test_indication_surfaces(
        self,
        mock_hyp: AsyncMock,
        mock_faers: AsyncMock,
        mock_canada: AsyncMock,
    ) -> None:
        mock_hyp.return_value = _make_hypothesis(indication_confounding=True)
        mock_faers.return_value = []
        mock_canada.return_value = []

        from hypokrates.cross.investigate import investigate

        result = await investigate("atorvastatin", "myalgia")
        assert any("INDICATION CONFOUNDING" in c for c in result.caveats)

    @patch("hypokrates.cross.investigate._run_canada_strata", new_callable=AsyncMock)
    @patch("hypokrates.cross.investigate._run_faers_strata", new_callable=AsyncMock)
    @patch("hypokrates.cross.investigate.hypothesis", new_callable=AsyncMock)
    async def test_coadmin_surfaces(
        self,
        mock_hyp: AsyncMock,
        mock_faers: AsyncMock,
        mock_canada: AsyncMock,
    ) -> None:
        mock_hyp.return_value = _make_hypothesis(
            coadmin=CoAdminAnalysis(
                profile=CoSuspectProfile(
                    drug="atorvastatin",
                    event="myalgia",
                    sample_size=50,
                    median_suspects=4.0,
                    mean_suspects=4.2,
                    co_admin_flag=True,
                ),
                verdict="co_admin_artifact",
            ),
        )
        mock_faers.return_value = []
        mock_canada.return_value = []

        from hypokrates.cross.investigate import investigate

        result = await investigate("atorvastatin", "myalgia")
        assert any("CO-ADMINISTRATION" in c for c in result.caveats)

    @patch("hypokrates.cross.investigate._run_canada_strata", new_callable=AsyncMock)
    @patch("hypokrates.cross.investigate._run_faers_strata", new_callable=AsyncMock)
    @patch("hypokrates.cross.investigate.hypothesis", new_callable=AsyncMock)
    async def test_no_caveats_clean(
        self,
        mock_hyp: AsyncMock,
        mock_faers: AsyncMock,
        mock_canada: AsyncMock,
    ) -> None:
        """Sinal limpo = zero caveats."""
        mock_hyp.return_value = _make_hypothesis(
            a=100,
            canada_reports=50,
            canada_signal=True,
            jader_reports=30,
            jader_signal=True,
        )
        mock_faers.return_value = [
            StratumSignal(
                source="FAERS",
                stratum_type="sex",
                stratum_value="F",
                drug_event_count=50,
                prr=3.0,
            ),
            StratumSignal(
                source="FAERS",
                stratum_type="sex",
                stratum_value="M",
                drug_event_count=50,
                prr=3.0,
            ),
            StratumSignal(
                source="FAERS",
                stratum_type="age_group",
                stratum_value="0-17",
                drug_event_count=25,
                prr=3.0,
            ),
            StratumSignal(
                source="FAERS",
                stratum_type="age_group",
                stratum_value="18-44",
                drug_event_count=25,
                prr=3.0,
            ),
            StratumSignal(
                source="FAERS",
                stratum_type="age_group",
                stratum_value="45-64",
                drug_event_count=25,
                prr=3.0,
            ),
            StratumSignal(
                source="FAERS",
                stratum_type="age_group",
                stratum_value="65+",
                drug_event_count=25,
                prr=3.0,
            ),
        ]
        mock_canada.return_value = []

        from hypokrates.cross.investigate import investigate

        result = await investigate("atorvastatin", "myalgia")
        assert result.caveats == []

    @patch("hypokrates.cross.investigate._run_canada_strata", new_callable=AsyncMock)
    @patch("hypokrates.cross.investigate._run_faers_strata", new_callable=AsyncMock)
    @patch("hypokrates.cross.investigate.hypothesis", new_callable=AsyncMock)
    async def test_empty_strata_graceful(
        self,
        mock_hyp: AsyncMock,
        mock_faers: AsyncMock,
        mock_canada: AsyncMock,
    ) -> None:
        """Sem strata = sem crash, só caveats de count."""
        mock_hyp.return_value = _make_hypothesis(a=3)
        mock_faers.return_value = []
        mock_canada.return_value = []

        from hypokrates.cross.investigate import investigate

        result = await investigate("atorvastatin", "myalgia")
        assert any("LOW COUNT" in c for c in result.caveats)
        # NON-REPLICATION não dispara (só 1 source)
        assert not any("NON-REPLICATION" in c for c in result.caveats)
