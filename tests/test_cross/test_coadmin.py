"""Testes para coadmin_analysis() e integração com hypothesis() — Layer 2 co-admin detection."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

from hypokrates.cross.api import coadmin_analysis, hypothesis
from hypokrates.cross.constants import OVERLAP_THRESHOLD, SPECIFICITY_RATIO_THRESHOLD
from hypokrates.faers.models import CoSuspectProfile, DrugCount, DrugsByEventResult
from hypokrates.models import MetaInfo
from hypokrates.stats.models import (
    ContingencyTable,
    DisproportionalityResult,
    SignalResult,
)


def _make_profile(
    *,
    median: float = 5.0,
    co_admin_flag: bool = True,
    top_co_drugs: list[tuple[str, int]] | None = None,
) -> CoSuspectProfile:
    """Builder para CoSuspectProfile."""
    default_co_drugs: list[tuple[str, int]] = [
        ("ROCURONIUM", 45),
        ("FENTANYL", 40),
        ("CEFAZOLIN", 35),
        ("MIDAZOLAM", 30),
        ("SUCCINYLCHOLINE", 20),
    ]
    return CoSuspectProfile(
        drug="PROPOFOL",
        event="ANAPHYLACTIC SHOCK",
        sample_size=50,
        median_suspects=median,
        mean_suspects=median,
        max_suspects=int(median) + 2,
        top_co_drugs=default_co_drugs if top_co_drugs is None else top_co_drugs,
        co_admin_flag=co_admin_flag,
    )


def _make_meta() -> MetaInfo:
    """Builder para MetaInfo."""
    from datetime import UTC, datetime

    return MetaInfo(
        source="test",
        query={},
        total_results=0,
        retrieved_at=datetime.now(UTC),
    )


def _make_drugs_by_event(
    names: list[str],
) -> DrugsByEventResult:
    """Builder para DrugsByEventResult com nomes de drogas."""
    return DrugsByEventResult(
        event="ANAPHYLACTIC SHOCK",
        drugs=[DrugCount(name=n, count=100 - i * 10) for i, n in enumerate(names)],
        meta=_make_meta(),
    )


def _make_signal_result(
    drug: str = "PROPOFOL",
    prr: float = 50.0,
    signal_detected: bool = True,
) -> SignalResult:
    """Builder para SignalResult."""
    return SignalResult(
        drug=drug,
        event="ANAPHYLACTIC SHOCK",
        table=ContingencyTable(a=100, b=1000, c=5000, d=1000000),
        prr=DisproportionalityResult(
            measure="PRR", value=prr, ci_lower=prr * 0.9, ci_upper=prr * 1.1, significant=True
        ),
        ror=DisproportionalityResult(
            measure="ROR", value=prr, ci_lower=prr * 0.9, ci_upper=prr * 1.1, significant=True
        ),
        ic=DisproportionalityResult(
            measure="IC", value=5.0, ci_lower=4.5, ci_upper=5.5, significant=True
        ),
        signal_detected=signal_detected,
        meta=_make_meta(),
    )


class TestCoAdminAnalysisVerdicts:
    """Testes dos verdicts de coadmin_analysis."""

    async def test_co_admin_artifact_high_overlap_low_specificity(self) -> None:
        """High overlap + PRR similar → co_admin_artifact."""
        profile = _make_profile()
        # Top event drugs incluem todos os co-suspects (overlap alto)
        dbe = _make_drugs_by_event(
            ["ROCURONIUM", "FENTANYL", "CEFAZOLIN", "PROPOFOL", "MIDAZOLAM"]
        )

        with (
            patch.object(
                __import__("hypokrates.faers.api", fromlist=["drugs_by_event"]),
                "drugs_by_event",
                new_callable=AsyncMock,
                return_value=dbe,
            ),
            patch(
                "hypokrates.cross.api.stats_api.signal",
                new_callable=AsyncMock,
                side_effect=lambda drug, event, **kw: _make_signal_result(drug, prr=48.0),
            ),
        ):
            result = await coadmin_analysis(
                "propofol",
                "anaphylactic shock",
                profile,
                drug_prr=50.0,
            )

        assert result.verdict == "co_admin_artifact"
        assert result.is_specific is False
        assert result.overlap_ratio > OVERLAP_THRESHOLD
        assert result.specificity_ratio is not None
        assert result.specificity_ratio <= SPECIFICITY_RATIO_THRESHOLD

    async def test_specific_low_overlap(self) -> None:
        """Low overlap → specific (drogas diferentes nas top do evento)."""
        profile = _make_profile()
        # Top event drugs são drogas completamente diferentes
        dbe = _make_drugs_by_event(["ISOTRETINOIN", "DOXYCYCLINE", "TRETINOIN", "SPIRONOLACTONE"])

        with patch(
            "hypokrates.cross.api.faers_api.drugs_by_event",
            new_callable=AsyncMock,
            return_value=dbe,
        ):
            result = await coadmin_analysis(
                "propofol",
                "anaphylactic shock",
                profile,
                drug_prr=50.0,
            )

        assert result.verdict == "specific"
        assert result.is_specific is True
        assert result.overlap_ratio < OVERLAP_THRESHOLD

    async def test_specific_high_specificity_ratio(self) -> None:
        """High overlap mas PRR muito maior que co-drugs → still specific."""
        profile = _make_profile()
        dbe = _make_drugs_by_event(["ROCURONIUM", "FENTANYL", "CEFAZOLIN", "MIDAZOLAM"])

        with (
            patch.object(
                __import__("hypokrates.faers.api", fromlist=["drugs_by_event"]),
                "drugs_by_event",
                new_callable=AsyncMock,
                return_value=dbe,
            ),
            patch(
                "hypokrates.cross.api.stats_api.signal",
                new_callable=AsyncMock,
                # Co-drugs têm PRR muito baixo → specificity ratio alto
                side_effect=lambda drug, event, **kw: _make_signal_result(drug, prr=5.0),
            ),
        ):
            result = await coadmin_analysis(
                "propofol",
                "anaphylactic shock",
                profile,
                drug_prr=50.0,  # 50/5 = 10 >> threshold
            )

        assert result.verdict == "specific"
        assert result.is_specific is True
        assert result.specificity_ratio is not None
        assert result.specificity_ratio > SPECIFICITY_RATIO_THRESHOLD

    async def test_inconclusive_no_drugs_by_event(self) -> None:
        """Sem drugs_by_event results → inconclusive."""
        profile = _make_profile()
        dbe = _make_drugs_by_event([])

        with patch(
            "hypokrates.cross.api.faers_api.drugs_by_event",
            new_callable=AsyncMock,
            return_value=dbe,
        ):
            result = await coadmin_analysis(
                "propofol", "anaphylactic shock", profile, drug_prr=50.0
            )

        assert result.verdict == "inconclusive"

    async def test_inconclusive_no_co_drugs(self) -> None:
        """Sem co-drugs no profile → inconclusive."""
        profile = _make_profile(top_co_drugs=[])
        dbe = _make_drugs_by_event(["ROCURONIUM", "FENTANYL"])

        with patch(
            "hypokrates.cross.api.faers_api.drugs_by_event",
            new_callable=AsyncMock,
            return_value=dbe,
        ):
            result = await coadmin_analysis(
                "propofol", "anaphylactic shock", profile, drug_prr=50.0
            )

        assert result.verdict == "inconclusive"

    async def test_not_flagged_profile_returns_specific(self) -> None:
        """co_admin_flag=False → specific (mesmo com overlap alto)."""
        profile = _make_profile(median=2.0, co_admin_flag=False)
        dbe = _make_drugs_by_event(["ROCURONIUM", "FENTANYL", "CEFAZOLIN", "MIDAZOLAM"])

        with patch(
            "hypokrates.cross.api.faers_api.drugs_by_event",
            new_callable=AsyncMock,
            return_value=dbe,
        ):
            result = await coadmin_analysis(
                "propofol", "anaphylactic shock", profile, drug_prr=50.0
            )

        assert result.verdict == "specific"

    async def test_co_signals_populated(self) -> None:
        """co_signals devem ter dados das co-drugs testadas."""
        profile = _make_profile()
        dbe = _make_drugs_by_event(["ROCURONIUM", "FENTANYL", "CEFAZOLIN", "MIDAZOLAM"])

        with (
            patch.object(
                __import__("hypokrates.faers.api", fromlist=["drugs_by_event"]),
                "drugs_by_event",
                new_callable=AsyncMock,
                return_value=dbe,
            ),
            patch(
                "hypokrates.cross.api.stats_api.signal",
                new_callable=AsyncMock,
                side_effect=lambda drug, event, **kw: _make_signal_result(drug, prr=45.0),
            ),
        ):
            result = await coadmin_analysis(
                "propofol", "anaphylactic shock", profile, drug_prr=50.0
            )

        assert len(result.co_signals) > 0
        co_drug_names = {cs.drug for cs in result.co_signals}
        assert "ROCURONIUM" in co_drug_names


def _make_pubmed() -> object:
    """Cria PubMedSearchResult mock."""
    from datetime import UTC, datetime

    from hypokrates.pubmed.models import PubMedSearchResult

    return PubMedSearchResult(
        total_count=10,
        articles=[],
        meta=MetaInfo(source="NCBI/PubMed", retrieved_at=datetime.now(UTC)),
    )


class TestHypothesisCoAdminIntegration:
    """Testes de integração: check_coadmin no hypothesis()."""

    @patch("hypokrates.cross.api.pubmed_api.search_papers")
    @patch("hypokrates.cross.api.stats_api.signal")
    async def test_coadmin_none_by_default(
        self, mock_signal: AsyncMock, mock_pubmed: AsyncMock
    ) -> None:
        """check_coadmin=False (default) → coadmin é None."""
        mock_signal.return_value = _make_signal_result()
        mock_pubmed.return_value = _make_pubmed()

        result = await hypothesis("propofol", "anaphylactic shock")

        assert result.coadmin is None

    @patch("hypokrates.cross.api.faers_api.co_suspect_profile")
    @patch("hypokrates.cross.api.pubmed_api.search_papers")
    @patch("hypokrates.cross.api.stats_api.signal")
    async def test_coadmin_layer1_only_when_no_signal(
        self, mock_signal: AsyncMock, mock_pubmed: AsyncMock, mock_profile: AsyncMock
    ) -> None:
        """Sem sinal FAERS → coadmin roda Layer 1 only (profile, sem comparative PRR)."""
        mock_signal.return_value = _make_signal_result(signal_detected=False, prr=0.5)
        mock_pubmed.return_value = _make_pubmed()
        mock_profile.return_value = _make_profile()

        result = await hypothesis("propofol", "anaphylactic shock", check_coadmin=True)

        assert result.coadmin is not None
        assert result.coadmin.verdict == "no_signal"
        mock_profile.assert_called_once()

    @patch("hypokrates.cross.api.faers_api.drugs_by_event")
    @patch("hypokrates.cross.api.faers_api.co_suspect_profile")
    @patch("hypokrates.cross.api.pubmed_api.search_papers")
    @patch("hypokrates.cross.api.stats_api.signal")
    async def test_coadmin_populated_when_signal_and_check(
        self,
        mock_signal: AsyncMock,
        mock_pubmed: AsyncMock,
        mock_profile: AsyncMock,
        mock_dbe: AsyncMock,
    ) -> None:
        """check_coadmin=True + signal detected → coadmin é populado."""
        mock_signal.return_value = _make_signal_result()
        mock_pubmed.return_value = _make_pubmed()
        mock_profile.return_value = _make_profile()
        mock_dbe.return_value = _make_drugs_by_event(["ROCURONIUM", "FENTANYL", "CEFAZOLIN"])

        result = await hypothesis("propofol", "anaphylactic shock", check_coadmin=True)

        assert result.coadmin is not None
        assert result.coadmin.profile.drug == "PROPOFOL"
        mock_profile.assert_called_once()
