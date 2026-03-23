"""Testes para hypokrates.cross.api — mock stats + pubmed."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from unittest.mock import AsyncMock, patch

import pytest

from hypokrates.config import configure
from hypokrates.cross.api import hypothesis
from hypokrates.cross.models import HypothesisClassification, HypothesisResult
from hypokrates.models import MetaInfo
from hypokrates.pubmed.models import PubMedArticle, PubMedSearchResult
from tests.helpers import make_signal


def _make_pubmed_result(
    count: int, articles: list[PubMedArticle] | None = None
) -> PubMedSearchResult:
    """Cria PubMedSearchResult mock."""
    return PubMedSearchResult(
        total_count=count,
        articles=articles or [],
        meta=MetaInfo(source="NCBI/PubMed", retrieved_at=datetime.now(UTC)),
    )


class TestHypothesisAPI:
    """Testes para hypothesis() — cruza sinal + literatura."""

    @pytest.fixture(autouse=True)
    def _disable_cache(self) -> None:
        configure(cache_enabled=False)

    @patch("hypokrates.cross.api.pubmed_api.search_papers")
    @patch("hypokrates.cross.api.stats_api.signal")
    async def test_novel_hypothesis(self, mock_signal: Any, mock_pubmed: Any) -> None:
        """Sinal detectado + 0 papers → novel_hypothesis."""
        mock_signal.return_value = make_signal(event="PRIS", detected=True)
        mock_pubmed.return_value = _make_pubmed_result(0)

        result = await hypothesis("propofol", "PRIS", use_cache=False)
        assert isinstance(result, HypothesisResult)
        assert result.classification == HypothesisClassification.NOVEL_HYPOTHESIS
        assert result.literature_count == 0
        assert "Novel hypothesis" in result.summary

    @patch("hypokrates.cross.api.pubmed_api.search_papers")
    @patch("hypokrates.cross.api.stats_api.signal")
    async def test_emerging_signal(self, mock_signal: Any, mock_pubmed: Any) -> None:
        """Sinal detectado + 3 papers → emerging_signal."""
        articles = [PubMedArticle(pmid=str(i), title=f"Paper {i}") for i in range(3)]
        mock_signal.return_value = make_signal(event="PRIS", detected=True)
        mock_pubmed.return_value = _make_pubmed_result(3, articles)

        result = await hypothesis("propofol", "PRIS", use_cache=False)
        assert result.classification == HypothesisClassification.EMERGING_SIGNAL
        assert result.literature_count == 3
        assert len(result.articles) == 3
        assert "Emerging" in result.summary

    @patch("hypokrates.cross.api.pubmed_api.search_papers")
    @patch("hypokrates.cross.api.stats_api.signal")
    async def test_known_association(self, mock_signal: Any, mock_pubmed: Any) -> None:
        """Sinal detectado + 10 papers → known_association."""
        articles = [PubMedArticle(pmid=str(i), title=f"Paper {i}") for i in range(5)]
        mock_signal.return_value = make_signal(event="PRIS", detected=True)
        mock_pubmed.return_value = _make_pubmed_result(10, articles)

        result = await hypothesis("propofol", "PRIS", use_cache=False)
        assert result.classification == HypothesisClassification.KNOWN_ASSOCIATION
        assert result.literature_count == 10
        assert "Known association" in result.summary

    @patch("hypokrates.cross.api.pubmed_api.search_papers")
    @patch("hypokrates.cross.api.stats_api.signal")
    async def test_no_signal_no_literature(self, mock_signal: Any, mock_pubmed: Any) -> None:
        """Sem sinal + 0 papers → no_signal."""
        mock_signal.return_value = make_signal(event="PRIS", detected=False)
        mock_pubmed.return_value = _make_pubmed_result(0)

        result = await hypothesis("aspirin", "HEADACHE", use_cache=False)
        assert result.classification == HypothesisClassification.NO_SIGNAL
        assert "No signal" in result.summary

    @patch("hypokrates.cross.api.pubmed_api.search_papers")
    @patch("hypokrates.cross.api.stats_api.signal")
    async def test_no_signal_with_literature(self, mock_signal: Any, mock_pubmed: Any) -> None:
        """Sem sinal FAERS + literatura substancial → emerging (FAERS diluído)."""
        mock_signal.return_value = make_signal(event="PRIS", detected=False)
        mock_pubmed.return_value = _make_pubmed_result(50)

        result = await hypothesis("aspirin", "HEADACHE", use_cache=False)
        assert result.classification == HypothesisClassification.EMERGING_SIGNAL

    @patch("hypokrates.cross.api.pubmed_api.search_papers")
    @patch("hypokrates.cross.api.stats_api.signal")
    async def test_custom_thresholds(self, mock_signal: Any, mock_pubmed: Any) -> None:
        """Thresholds customizados mudam classificação."""
        mock_signal.return_value = make_signal(event="PRIS", detected=True)
        mock_pubmed.return_value = _make_pubmed_result(3)

        # Default: 3 papers → emerging. Com novel_max=5 → novel.
        result = await hypothesis("propofol", "PRIS", novel_max=5, use_cache=False)
        assert result.classification == HypothesisClassification.NOVEL_HYPOTHESIS
        assert result.thresholds_used["novel_max"] == 5

    @patch("hypokrates.cross.api.pubmed_api.search_papers")
    @patch("hypokrates.cross.api.stats_api.signal")
    async def test_evidence_block_present(self, mock_signal: Any, mock_pubmed: Any) -> None:
        """HypothesisResult tem EvidenceBlock completo."""
        mock_signal.return_value = make_signal(event="PRIS", detected=True)
        mock_pubmed.return_value = _make_pubmed_result(0)

        result = await hypothesis("propofol", "PRIS", use_cache=False)
        assert result.evidence.source == "FAERS+PubMed"
        assert result.evidence.methodology is not None
        assert result.evidence.confidence is not None
        assert len(result.evidence.limitations) > 0

    @patch("hypokrates.cross.api.pubmed_api.search_papers")
    @patch("hypokrates.cross.api.stats_api.signal")
    async def test_thresholds_in_result(self, mock_signal: Any, mock_pubmed: Any) -> None:
        """thresholds_used reflete os valores usados."""
        mock_signal.return_value = make_signal(event="PRIS", detected=True)
        mock_pubmed.return_value = _make_pubmed_result(0)

        result = await hypothesis(
            "propofol", "PRIS", novel_max=2, emerging_max=10, use_cache=False
        )
        assert result.thresholds_used == {"novel_max": 2, "emerging_max": 10}

    @patch("hypokrates.cross.api.pubmed_api.search_papers")
    @patch("hypokrates.cross.api.stats_api.signal")
    async def test_boundary_novel_to_emerging(self, mock_signal: Any, mock_pubmed: Any) -> None:
        """Exatamente novel_max papers → novel. novel_max+1 → emerging."""
        mock_signal.return_value = make_signal(event="PRIS", detected=True)

        # At boundary: 0 papers com novel_max=0 → novel
        mock_pubmed.return_value = _make_pubmed_result(0)
        r1 = await hypothesis("propofol", "PRIS", novel_max=0, use_cache=False)
        assert r1.classification == HypothesisClassification.NOVEL_HYPOTHESIS

        # Just above: 1 paper com novel_max=0 → emerging
        mock_pubmed.return_value = _make_pubmed_result(1)
        r2 = await hypothesis("propofol", "PRIS", novel_max=0, use_cache=False)
        assert r2.classification == HypothesisClassification.EMERGING_SIGNAL

    @patch("hypokrates.cross.api.pubmed_api.search_papers")
    @patch("hypokrates.cross.api.stats_api.signal")
    async def test_boundary_emerging_to_known(self, mock_signal: Any, mock_pubmed: Any) -> None:
        """Exatamente emerging_max papers → emerging. emerging_max+1 → known."""
        mock_signal.return_value = make_signal(event="PRIS", detected=True)

        # At boundary: 5 papers → emerging
        mock_pubmed.return_value = _make_pubmed_result(5)
        r1 = await hypothesis("propofol", "PRIS", emerging_max=5, use_cache=False)
        assert r1.classification == HypothesisClassification.EMERGING_SIGNAL

        # Just above: 6 papers → known
        mock_pubmed.return_value = _make_pubmed_result(6)
        r2 = await hypothesis("propofol", "PRIS", emerging_max=5, use_cache=False)
        assert r2.classification == HypothesisClassification.KNOWN_ASSOCIATION

    @patch("hypokrates.cross.api.pubmed_api.search_papers")
    @patch("hypokrates.cross.api.stats_api.signal")
    async def test_default_no_label_fields(self, mock_signal: Any, mock_pubmed: Any) -> None:
        """Sem check_label/check_trials → campos são None."""
        mock_signal.return_value = make_signal(event="PRIS", detected=True)
        mock_pubmed.return_value = _make_pubmed_result(0)

        result = await hypothesis("propofol", "PRIS", use_cache=False)
        assert result.in_label is None
        assert result.label_detail is None
        assert result.active_trials is None
        assert result.trials_detail is None


def _make_label_events(
    *, drug: str = "propofol", events: list[str] | None = None, raw_text: str = ""
) -> Any:
    from hypokrates.dailymed.models import LabelEventsResult

    return LabelEventsResult(
        drug=drug,
        set_id="test-set-id",
        events=events or [],
        raw_text=raw_text,
        meta=MetaInfo(source="DailyMed/FDA", retrieved_at=datetime.now(UTC)),
    )


class TestHypothesisWithLabel:
    """hypothesis() com check_label=True."""

    @pytest.fixture(autouse=True)
    def _disable_cache(self) -> None:
        configure(cache_enabled=False)

    @patch("hypokrates.dailymed.api.label_events", new_callable=AsyncMock)
    @patch("hypokrates.cross.api.pubmed_api.search_papers")
    @patch("hypokrates.cross.api.stats_api.signal")
    async def test_in_label_upgrades_novel_to_emerging(
        self, mock_signal: Any, mock_pubmed: Any, mock_label_events: AsyncMock
    ) -> None:
        """Signal + in_label=True + 0 papers → EMERGING (não NOVEL)."""
        mock_signal.return_value = make_signal(event="PRIS", detected=True)
        mock_pubmed.return_value = _make_pubmed_result(0)
        mock_label_events.return_value = _make_label_events(
            events=["Bradycardia", "Hypotension"],
        )

        result = await hypothesis("propofol", "bradycardia", check_label=True, use_cache=False)

        assert result.in_label is True
        assert result.classification == HypothesisClassification.EMERGING_SIGNAL

    @patch("hypokrates.dailymed.api.label_events", new_callable=AsyncMock)
    @patch("hypokrates.cross.api.pubmed_api.search_papers")
    @patch("hypokrates.cross.api.stats_api.signal")
    async def test_not_in_label_stays_novel(
        self, mock_signal: Any, mock_pubmed: Any, mock_label_events: AsyncMock
    ) -> None:
        """Signal + in_label=False + 0 papers → NOVEL (confirmado)."""
        mock_signal.return_value = make_signal(event="PRIS", detected=True)
        mock_pubmed.return_value = _make_pubmed_result(0)
        mock_label_events.return_value = _make_label_events(events=["Hypotension"])

        result = await hypothesis(
            "propofol", "serotonin syndrome", check_label=True, use_cache=False
        )

        assert result.in_label is False
        assert result.classification == HypothesisClassification.NOVEL_HYPOTHESIS

    @patch("hypokrates.dailymed.api.label_events", new_callable=AsyncMock)
    @patch("hypokrates.cross.api.pubmed_api.search_papers")
    @patch("hypokrates.cross.api.stats_api.signal")
    async def test_label_detail_populated(
        self, mock_signal: Any, mock_pubmed: Any, mock_label_events: AsyncMock
    ) -> None:
        """label_detail reflete resultado."""
        mock_signal.return_value = make_signal(event="PRIS", detected=True)
        mock_pubmed.return_value = _make_pubmed_result(0)
        mock_label_events.return_value = _make_label_events(
            events=["Bradycardia", "Hypotension"],
        )

        result = await hypothesis("propofol", "bradycardia", check_label=True, use_cache=False)

        assert result.label_detail is not None
        assert "Matched:" in result.label_detail
        assert "label" in result.summary.lower()


class TestHypothesisWithTrials:
    """hypothesis() com check_trials=True."""

    @pytest.fixture(autouse=True)
    def _disable_cache(self) -> None:
        configure(cache_enabled=False)

    @patch("hypokrates.trials.api.search_trials", new_callable=AsyncMock)
    @patch("hypokrates.cross.api.pubmed_api.search_papers")
    @patch("hypokrates.cross.api.stats_api.signal")
    async def test_trials_info_populated(
        self, mock_signal: Any, mock_pubmed: Any, mock_search_trials: AsyncMock
    ) -> None:
        """check_trials → active_trials e trials_detail populados."""
        from hypokrates.trials.models import ClinicalTrial, TrialsResult

        mock_signal.return_value = make_signal(event="PRIS", detected=True)
        mock_pubmed.return_value = _make_pubmed_result(0)
        mock_search_trials.return_value = TrialsResult(
            drug="propofol",
            event="hypotension",
            total_count=3,
            active_count=2,
            trials=[
                ClinicalTrial(nct_id="NCT001", title="Test", status="RECRUITING"),
                ClinicalTrial(nct_id="NCT002", title="Test2", status="ACTIVE_NOT_RECRUITING"),
            ],
            meta=MetaInfo(source="ClinicalTrials.gov", retrieved_at=datetime.now(UTC)),
        )

        result = await hypothesis("propofol", "hypotension", check_trials=True, use_cache=False)

        assert result.active_trials == 2
        assert result.trials_detail is not None
        assert "3 trials found" in result.trials_detail


class TestHypothesisWithDrugBank:
    """hypothesis() com check_drugbank=True."""

    @pytest.fixture(autouse=True)
    def _disable_cache(self) -> None:
        configure(cache_enabled=False)

    @patch("hypokrates.drugbank.api.drug_info", new_callable=AsyncMock)
    @patch("hypokrates.cross.api.pubmed_api.search_papers")
    @patch("hypokrates.cross.api.stats_api.signal")
    async def test_drugbank_fields_populated(
        self, mock_signal: Any, mock_pubmed: Any, mock_drug_info: AsyncMock
    ) -> None:
        """check_drugbank → mechanism, interactions, enzymes populados."""
        from hypokrates.drugbank.models import (
            DrugBankInfo,
            DrugEnzyme,
            DrugInteraction,
            DrugTarget,
        )

        mock_signal.return_value = make_signal(event="PRIS", detected=True)
        mock_pubmed.return_value = _make_pubmed_result(0)
        mock_drug_info.return_value = DrugBankInfo(
            drugbank_id="DB00818",
            name="Propofol",
            mechanism_of_action="GABA-A receptor potentiator",
            targets=[DrugTarget(name="GABRA1", gene_name="GABRA1", actions=["potentiator"])],
            enzymes=[
                DrugEnzyme(name="CYP2B6", gene_name="CYP2B6"),
                DrugEnzyme(name="UGT1A9", gene_name="UGT1A9"),
            ],
            interactions=[
                DrugInteraction(partner_id="DB00813", partner_name="Fentanyl"),
                DrugInteraction(partner_id="DB01236", partner_name="Sevoflurane"),
            ],
        )

        result = await hypothesis("propofol", "PRIS", check_drugbank=True, use_cache=False)

        assert result.mechanism == "GABA-A receptor potentiator"
        assert "Fentanyl" in result.interactions
        assert "CYP2B6" in result.enzymes
        assert "UGT1A9" in result.enzymes

    @patch("hypokrates.cross.api.pubmed_api.search_papers")
    @patch("hypokrates.cross.api.stats_api.signal")
    async def test_drugbank_with_cache(self, mock_signal: Any, mock_pubmed: Any) -> None:
        """_drugbank_cache é usado em vez de chamar API."""
        from hypokrates.drugbank.models import DrugBankInfo

        mock_signal.return_value = make_signal(event="PRIS", detected=True)
        mock_pubmed.return_value = _make_pubmed_result(0)

        cache = DrugBankInfo(
            drugbank_id="DB00818",
            name="Propofol",
            mechanism_of_action="Cached mechanism",
        )

        result = await hypothesis(
            "propofol", "PRIS", check_drugbank=True, _drugbank_cache=cache, use_cache=False
        )

        assert result.mechanism == "Cached mechanism"

    @patch("hypokrates.drugbank.api.drug_info", new_callable=AsyncMock)
    @patch("hypokrates.cross.api.pubmed_api.search_papers")
    @patch("hypokrates.cross.api.stats_api.signal")
    async def test_drugbank_not_found(
        self, mock_signal: Any, mock_pubmed: Any, mock_drug_info: AsyncMock
    ) -> None:
        """DrugBank não encontrou a droga → campos None/empty."""
        mock_signal.return_value = make_signal(event="PRIS", detected=True)
        mock_pubmed.return_value = _make_pubmed_result(0)
        mock_drug_info.return_value = None

        result = await hypothesis("unknown_drug", "PRIS", check_drugbank=True, use_cache=False)

        assert result.mechanism is None
        assert result.interactions == []
        assert result.enzymes == []


class TestHypothesisGracefulDegradation:
    """hypothesis() continua funcionando quando enrichments opcionais falham."""

    @pytest.fixture(autouse=True)
    def _disable_cache(self) -> None:
        configure(cache_enabled=False)

    @patch("hypokrates.dailymed.api.label_events", new_callable=AsyncMock)
    @patch("hypokrates.cross.api.pubmed_api.search_papers")
    @patch("hypokrates.cross.api.stats_api.signal")
    async def test_label_failure_degrades_gracefully(
        self, mock_signal: AsyncMock, mock_pubmed: AsyncMock, mock_label_events: AsyncMock
    ) -> None:
        """label_events exception → in_label stays None, result still returned."""
        mock_signal.return_value = make_signal(event="PRIS", detected=True)
        mock_pubmed.return_value = _make_pubmed_result(0)
        mock_label_events.side_effect = Exception("DailyMed down")

        result = await hypothesis("propofol", "bradycardia", check_label=True, use_cache=False)

        assert isinstance(result, HypothesisResult)
        assert result.in_label is None
        assert result.label_detail is None

    @patch("hypokrates.trials.api.search_trials", new_callable=AsyncMock)
    @patch("hypokrates.cross.api.pubmed_api.search_papers")
    @patch("hypokrates.cross.api.stats_api.signal")
    async def test_trials_failure_degrades_gracefully(
        self, mock_signal: AsyncMock, mock_pubmed: AsyncMock, mock_trials: AsyncMock
    ) -> None:
        """check_trials exception → active_trials stays None."""
        mock_signal.return_value = make_signal(event="PRIS", detected=True)
        mock_pubmed.return_value = _make_pubmed_result(0)
        mock_trials.side_effect = Exception("ClinicalTrials.gov down")

        result = await hypothesis("propofol", "bradycardia", check_trials=True, use_cache=False)

        assert isinstance(result, HypothesisResult)
        assert result.active_trials is None
        assert result.trials_detail is None

    @patch("hypokrates.opentargets.api.drug_safety_score", new_callable=AsyncMock)
    @patch("hypokrates.cross.api.pubmed_api.search_papers")
    @patch("hypokrates.cross.api.stats_api.signal")
    async def test_opentargets_failure_degrades_gracefully(
        self, mock_signal: AsyncMock, mock_pubmed: AsyncMock, mock_ot: AsyncMock
    ) -> None:
        """check_opentargets exception → ot_llr stays None."""
        mock_signal.return_value = make_signal(event="PRIS", detected=True)
        mock_pubmed.return_value = _make_pubmed_result(0)
        mock_ot.side_effect = Exception("OpenTargets down")

        result = await hypothesis(
            "propofol", "bradycardia", check_opentargets=True, use_cache=False
        )

        assert isinstance(result, HypothesisResult)
        assert result.ot_llr is None

    @patch("hypokrates.chembl.api.drug_mechanism", new_callable=AsyncMock)
    @patch("hypokrates.cross.api.pubmed_api.search_papers")
    @patch("hypokrates.cross.api.stats_api.signal")
    async def test_chembl_failure_degrades_gracefully(
        self, mock_signal: AsyncMock, mock_pubmed: AsyncMock, mock_chembl: AsyncMock
    ) -> None:
        """check_chembl exception → mechanism stays None."""
        mock_signal.return_value = make_signal(event="PRIS", detected=True)
        mock_pubmed.return_value = _make_pubmed_result(0)
        mock_chembl.side_effect = Exception("ChEMBL down")

        result = await hypothesis("propofol", "bradycardia", check_chembl=True, use_cache=False)

        assert isinstance(result, HypothesisResult)
        assert result.mechanism is None

    @patch("hypokrates.cross.api.faers_api.co_suspect_profile", new_callable=AsyncMock)
    @patch("hypokrates.cross.api.pubmed_api.search_papers")
    @patch("hypokrates.cross.api.stats_api.signal")
    async def test_coadmin_failure_degrades_gracefully(
        self, mock_signal: AsyncMock, mock_pubmed: AsyncMock, mock_coadmin: AsyncMock
    ) -> None:
        """check_coadmin exception → coadmin stays None."""
        mock_signal.return_value = make_signal(event="PRIS", detected=True)
        mock_pubmed.return_value = _make_pubmed_result(0)
        mock_coadmin.side_effect = Exception("FAERS co-suspect down")

        result = await hypothesis("propofol", "bradycardia", check_coadmin=True, use_cache=False)

        assert isinstance(result, HypothesisResult)
        assert result.coadmin is None

    @patch("hypokrates.dailymed.api.label_events", new_callable=AsyncMock)
    @patch("hypokrates.trials.api.search_trials", new_callable=AsyncMock)
    @patch("hypokrates.cross.api.pubmed_api.search_papers")
    @patch("hypokrates.cross.api.stats_api.signal")
    async def test_label_and_trials_both_fail(
        self,
        mock_signal: AsyncMock,
        mock_pubmed: AsyncMock,
        mock_trials: AsyncMock,
        mock_label_events: AsyncMock,
    ) -> None:
        """label_events + search_trials both fail → both stay None."""
        mock_signal.return_value = make_signal(event="PRIS", detected=True)
        mock_pubmed.return_value = _make_pubmed_result(0)
        mock_label_events.side_effect = Exception("DailyMed down")
        mock_trials.side_effect = Exception("Trials down")

        result = await hypothesis(
            "propofol", "bradycardia", check_label=True, check_trials=True, use_cache=False
        )

        assert isinstance(result, HypothesisResult)
        assert result.in_label is None
        assert result.active_trials is None


class TestHypothesisWithOpenTargets:
    """hypothesis() com check_opentargets=True."""

    @pytest.fixture(autouse=True)
    def _disable_cache(self) -> None:
        configure(cache_enabled=False)

    @patch("hypokrates.opentargets.api.drug_safety_score", new_callable=AsyncMock)
    @patch("hypokrates.cross.api.pubmed_api.search_papers")
    @patch("hypokrates.cross.api.stats_api.signal")
    async def test_ot_llr_populated(
        self, mock_signal: Any, mock_pubmed: Any, mock_ot_score: AsyncMock
    ) -> None:
        """check_opentargets → ot_llr populado."""
        mock_signal.return_value = make_signal(event="PRIS", detected=True)
        mock_pubmed.return_value = _make_pubmed_result(0)
        mock_ot_score.return_value = 18.72

        result = await hypothesis(
            "propofol", "bradycardia", check_opentargets=True, use_cache=False
        )

        assert result.ot_llr == 18.72

    @patch("hypokrates.opentargets.api.drug_safety_score", new_callable=AsyncMock)
    @patch("hypokrates.cross.api.pubmed_api.search_papers")
    @patch("hypokrates.cross.api.stats_api.signal")
    async def test_ot_not_found(
        self, mock_signal: Any, mock_pubmed: Any, mock_ot_score: AsyncMock
    ) -> None:
        """OpenTargets não encontrou o par → ot_llr=None."""
        mock_signal.return_value = make_signal(event="PRIS", detected=True)
        mock_pubmed.return_value = _make_pubmed_result(0)
        mock_ot_score.return_value = None

        result = await hypothesis("unknown", "unknown", check_opentargets=True, use_cache=False)

        assert result.ot_llr is None

    @patch("hypokrates.cross.api.pubmed_api.search_papers")
    @patch("hypokrates.cross.api.stats_api.signal")
    async def test_ot_with_cache(self, mock_signal: Any, mock_pubmed: Any) -> None:
        """_ot_safety_cache é usado em vez de chamar API."""
        from hypokrates.opentargets.models import OTAdverseEvent, OTDrugSafety

        mock_signal.return_value = make_signal(event="PRIS", detected=True)
        mock_pubmed.return_value = _make_pubmed_result(0)

        cache = OTDrugSafety(
            drug_name="propofol",
            chembl_id="CHEMBL526",
            adverse_events=[
                OTAdverseEvent(name="BRADYCARDIA", count=980, log_lr=18.72),
            ],
            meta=MetaInfo(source="OpenTargets", retrieved_at=datetime.now(UTC)),
        )

        result = await hypothesis(
            "propofol",
            "bradycardia",
            check_opentargets=True,
            _ot_safety_cache=cache,
            use_cache=False,
        )

        assert result.ot_llr == 18.72


class TestCompareSignalsTargetEvent:
    """compare_signals() com target_event."""

    @pytest.fixture(autouse=True)
    def _disable_cache(self) -> None:
        configure(cache_enabled=False)

    def _make_faers_result(self, events: list[str]) -> Any:
        from hypokrates.faers.models import FAERSResult
        from hypokrates.models import AdverseEvent

        return FAERSResult(
            events=[AdverseEvent(term=e, count=100 - i) for i, e in enumerate(events)],
            meta=MetaInfo(source="FAERS", retrieved_at=datetime.now(UTC)),
        )

    @patch("hypokrates.cross.api.faers_api.top_events", new_callable=AsyncMock)
    @patch("hypokrates.cross.api.stats_api.signal", new_callable=AsyncMock)
    async def test_target_event_included(
        self, mock_signal: AsyncMock, mock_top: AsyncMock
    ) -> None:
        """target_event ausente do top -> aparece no resultado (canonicalizado)."""
        mock_top.return_value = self._make_faers_result(["NAUSEA", "HEADACHE"])
        mock_signal.return_value = make_signal(detected=True)

        from hypokrates.cross.api import compare_signals
        from hypokrates.vocab.meddra import canonical_term

        target = "ANAPHYLACTIC REACTION"
        result = await compare_signals(
            "drugA", "drugB", target_event=target, top_n=2, use_cache=False
        )
        event_names = {item.event.upper() for item in result.items}
        assert canonical_term(target) in event_names

    @patch("hypokrates.cross.api.faers_api.top_events", new_callable=AsyncMock)
    @patch("hypokrates.cross.api.stats_api.signal", new_callable=AsyncMock)
    async def test_target_event_dedup(self, mock_signal: AsyncMock, mock_top: AsyncMock) -> None:
        """target_event ja no top (ou sinonimo) -> sem duplicata."""
        mock_top.return_value = self._make_faers_result(["NAUSEA", "HEADACHE"])
        mock_signal.return_value = make_signal(detected=True)

        from hypokrates.cross.api import compare_signals
        from hypokrates.vocab.meddra import canonical_term

        canon = canonical_term("NAUSEA")
        result = await compare_signals(
            "drugA", "drugB", target_event="NAUSEA", top_n=2, use_cache=False
        )
        canon_count = sum(1 for item in result.items if item.event.upper() == canon)
        assert canon_count == 1

    @patch("hypokrates.cross.api.stats_api.signal", new_callable=AsyncMock)
    async def test_target_event_ignored_with_manual(self, mock_signal: AsyncMock) -> None:
        """events=[...] + target_event -> target_event ignorado."""
        mock_signal.return_value = make_signal(detected=True)

        from hypokrates.cross.api import compare_signals

        result = await compare_signals(
            "drugA",
            "drugB",
            events=["NAUSEA"],
            target_event="HEADACHE",
            use_cache=False,
        )
        event_names = {item.event.upper() for item in result.items}
        assert "HEADACHE" not in event_names
        assert "NAUSEA" in event_names
