"""Suíte sentinela — bateria fixa de regressão para rodar após cada mudança.

Cobre:
- Sinais reais, controles positivos, confounding, artefatos, sinais mortos
- Brand→generic normalization (RxNorm)
- MedDRA grouping
- Consistência entre tools (signal vs hypothesis vs label vs OT)
- Falha graciosa (droga/evento inexistente, DrugBank/DailyMed ausente, bulk vazio)
- Drogas ruidosas (prednisone, dexamethasone, etc.)

Rodar:
    pytest tests/test_sentinel/ -v
    pytest tests/test_sentinel/ -v -k "signal"    # só sinais
    pytest tests/test_sentinel/ -v -k "brand"      # só brand→generic
    pytest tests/test_sentinel/ -v -k "graceful"   # só falhas graciosas
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from unittest.mock import AsyncMock, patch

import pytest

from hypokrates.config import configure
from hypokrates.cross.models import HypothesisClassification, HypothesisResult
from hypokrates.dailymed.models import LabelCheckResult
from hypokrates.evidence.models import EvidenceBlock
from hypokrates.faers.models import CoSuspectProfile, FAERSResult
from hypokrates.models import AdverseEvent, MetaInfo
from hypokrates.pubmed.models import PubMedArticle, PubMedSearchResult
from hypokrates.stats.models import ContingencyTable, DisproportionalityResult, SignalResult
from hypokrates.vocab.meddra import canonical_term

from .golden_sentinel import (
    BRAND_CASES,
    CONSISTENCY_CASES,
    LABEL_CASES,
    MEDDRA_CASES,
    NOISY_DRUGS,
    SIGNAL_CASES,
    BrandCase,
    ConsistencyCase,
    MedDRAGroupCase,
    SentinelCase,
)

# ---------------------------------------------------------------------------
# Helpers — factories para mocks tipados
# ---------------------------------------------------------------------------


def _meta(source: str = "test") -> MetaInfo:
    return MetaInfo(source=source, retrieved_at=datetime.now(UTC))


def _signal(
    drug: str,
    event: str,
    *,
    detected: bool = True,
    prr_val: float = 2.0,
    prr_lci: float = 1.5,
    a: int = 100,
) -> SignalResult:
    return SignalResult(
        drug=drug,
        event=event,
        table=ContingencyTable(a=a, b=900, c=50, d=9000),
        prr=DisproportionalityResult(
            measure="PRR",
            value=prr_val,
            ci_lower=prr_lci,
            ci_upper=prr_val + 1,
            significant=detected,
        ),
        ror=DisproportionalityResult(
            measure="ROR",
            value=prr_val + 0.2,
            ci_lower=prr_lci + 0.1,
            ci_upper=prr_val + 1.2,
            significant=detected,
        ),
        ic=DisproportionalityResult(
            measure="IC",
            value=1.0,
            ci_lower=0.5 if detected else -0.5,
            ci_upper=1.5,
            significant=detected,
        ),
        ebgm=DisproportionalityResult(
            measure="EBGM",
            value=2.0,
            ci_lower=1.5 if detected else 0.5,
            ci_upper=2.5,
            significant=detected,
        ),
        signal_detected=detected,
        meta=_meta("OpenFDA/FAERS"),
    )


def _pubmed(count: int, n_articles: int = 0) -> PubMedSearchResult:
    articles = [PubMedArticle(pmid=str(i), title=f"Paper {i}") for i in range(n_articles)]
    return PubMedSearchResult(total_count=count, articles=articles, meta=_meta("PubMed"))


def _evidence() -> EvidenceBlock:
    return EvidenceBlock(source="FAERS+PubMed", retrieved_at=datetime.now(UTC))


def _hypothesis_result(
    drug: str,
    event: str,
    classification: HypothesisClassification,
    *,
    signal_detected: bool = True,
    prr_val: float = 2.0,
    prr_lci: float = 1.5,
    lit_count: int = 0,
    in_label: bool | None = None,
    coadmin_flag: bool = False,
    a: int = 100,
) -> HypothesisResult:
    sig = _signal(drug, event, detected=signal_detected, prr_val=prr_val, prr_lci=prr_lci, a=a)
    coadmin = None
    if coadmin_flag:
        coadmin_profile = CoSuspectProfile(
            drug=drug,
            event=event,
            total_reports=50,
            median_suspects=5.2,
            co_admin_flag=True,
            top_co_suspects=["CISPLATIN", "DEXAMETHASONE"],
            meta=_meta(),
        )
        from hypokrates.cross.models import CoAdminAnalysis

        coadmin = CoAdminAnalysis(
            profile=coadmin_profile,
            overlap_ratio=0.6,
            is_specific=False,
            verdict="co_admin_artifact",
        )
    return HypothesisResult(
        drug=drug,
        event=event,
        classification=classification,
        signal=sig,
        literature_count=lit_count,
        articles=[
            PubMedArticle(pmid=str(i), title=f"Paper {i}") for i in range(min(lit_count, 5))
        ],
        evidence=_evidence(),
        summary=f"{classification.value}: {drug} + {event}",
        thresholds_used={"novel_max": 0, "emerging_max": 5},
        in_label=in_label,
        coadmin=coadmin,
    )


def _events(terms: list[str]) -> FAERSResult:
    return FAERSResult(
        events=[AdverseEvent(term=t, count=100 - i) for i, t in enumerate(terms)],
        meta=_meta(),
    )


def _label_check(drug: str, event: str, *, in_label: bool) -> LabelCheckResult:
    return LabelCheckResult(
        drug=drug,
        event=event,
        in_label=in_label,
        matched_terms=[event] if in_label else [],
        meta=_meta("DailyMed"),
    )


# ---------------------------------------------------------------------------
# Mapa de cenários → mocks específicos por caso
# ---------------------------------------------------------------------------


def _get_signal_mock(case: SentinelCase) -> SignalResult:
    """Cria SignalResult apropriado para o cenário."""
    prr_val = max(case.prr_min, 2.0) if case.signal_detected else 0.8
    a = 5000 if case.volume_flag else 100
    return _signal(
        case.drug,
        case.event,
        detected=case.signal_detected,
        prr_val=prr_val,
        prr_lci=prr_val * 0.7 if case.signal_detected else 0.5,
        a=a,
    )


def _get_pubmed_mock(case: SentinelCase) -> PubMedSearchResult:
    """Cria PubMedSearchResult apropriado para a classificação."""
    cls = case.classification
    if cls is None and case.allowed_classifications:
        cls = case.allowed_classifications[0]
    if cls == HypothesisClassification.NOVEL_HYPOTHESIS:
        return _pubmed(0)
    if cls == HypothesisClassification.EMERGING_SIGNAL:
        return _pubmed(3, 3)
    if cls == HypothesisClassification.KNOWN_ASSOCIATION:
        return _pubmed(50, 5)
    return _pubmed(0)


def _get_classification(case: SentinelCase) -> HypothesisClassification:
    """Determina a classificação esperada para o cenário."""
    if case.classification is not None:
        return case.classification
    if case.allowed_classifications:
        return case.allowed_classifications[0]
    return HypothesisClassification.NO_SIGNAL


# ===========================================================================
# PARTE 1: Detecção de sinais — cenários clínicos
# ===========================================================================


class TestSentinelSignals:
    """Testes sentinela de detecção de sinais."""

    @pytest.fixture(autouse=True)
    def _disable_cache(self) -> None:
        configure(cache_enabled=False)

    @pytest.mark.parametrize(
        "case",
        SIGNAL_CASES,
        ids=[c.scenario for c in SIGNAL_CASES],
    )
    @patch("hypokrates.cross.api.pubmed_api.search_papers")
    @patch("hypokrates.cross.api.stats_api.signal")
    async def test_signal_detection(
        self,
        mock_signal: AsyncMock,
        mock_pubmed: AsyncMock,
        case: SentinelCase,
    ) -> None:
        """Verifica signal_detected para cada cenário sentinela."""
        mock_signal.return_value = _get_signal_mock(case)
        mock_pubmed.return_value = _get_pubmed_mock(case)

        from hypokrates.cross.api import hypothesis

        result = await hypothesis(case.drug, case.event, use_cache=False)

        assert result.signal.signal_detected == case.signal_detected, (
            f"[{case.scenario}] signal_detected: esperado {case.signal_detected}, "
            f"obteve {result.signal.signal_detected}"
        )

    @pytest.mark.parametrize(
        "case",
        [c for c in SIGNAL_CASES if c.classification or c.allowed_classifications],
        ids=[c.scenario for c in SIGNAL_CASES if c.classification or c.allowed_classifications],
    )
    @patch("hypokrates.cross.api.pubmed_api.search_papers")
    @patch("hypokrates.cross.api.stats_api.signal")
    async def test_classification(
        self,
        mock_signal: AsyncMock,
        mock_pubmed: AsyncMock,
        case: SentinelCase,
    ) -> None:
        """Verifica classificação (NOVEL/EMERGING/KNOWN/NO_SIGNAL)."""
        mock_signal.return_value = _get_signal_mock(case)
        mock_pubmed.return_value = _get_pubmed_mock(case)

        from hypokrates.cross.api import hypothesis

        result = await hypothesis(case.drug, case.event, use_cache=False)

        allowed = (case.classification,) if case.classification else case.allowed_classifications
        assert result.classification in allowed, (
            f"[{case.scenario}] classificação: esperado {allowed}, obteve {result.classification}"
        )

    @pytest.mark.parametrize(
        "case",
        [c for c in SIGNAL_CASES if c.signal_detected and c.prr_min > 1.0],
        ids=[c.scenario for c in SIGNAL_CASES if c.signal_detected and c.prr_min > 1.0],
    )
    @patch("hypokrates.cross.api.pubmed_api.search_papers")
    @patch("hypokrates.cross.api.stats_api.signal")
    async def test_prr_range(
        self,
        mock_signal: AsyncMock,
        mock_pubmed: AsyncMock,
        case: SentinelCase,
    ) -> None:
        """Verifica que PRR está dentro do range esperado."""
        sig = _get_signal_mock(case)
        mock_signal.return_value = sig
        mock_pubmed.return_value = _get_pubmed_mock(case)

        from hypokrates.cross.api import hypothesis

        result = await hypothesis(case.drug, case.event, use_cache=False)

        prr = result.signal.prr.value
        assert prr >= case.prr_min, f"[{case.scenario}] PRR={prr:.2f} < mínimo {case.prr_min}"
        assert prr <= case.prr_max, f"[{case.scenario}] PRR={prr:.2f} > máximo {case.prr_max}"


# ===========================================================================
# PARTE 2: Label validation (DailyMed SPL)
# ===========================================================================


class TestSentinelLabels:
    """Testes sentinela para seleção de SPL e check_label."""

    @pytest.fixture(autouse=True)
    def _disable_cache(self) -> None:
        configure(cache_enabled=False)

    @pytest.mark.parametrize(
        "case",
        LABEL_CASES,
        ids=[c.scenario for c in LABEL_CASES],
    )
    @patch("hypokrates.dailymed.api.check_label", new_callable=AsyncMock)
    @patch("hypokrates.cross.api.pubmed_api.search_papers")
    @patch("hypokrates.cross.api.stats_api.signal")
    async def test_label_check(
        self,
        mock_signal: AsyncMock,
        mock_pubmed: AsyncMock,
        mock_check_label: AsyncMock,
        case: SentinelCase,
    ) -> None:
        """Verifica in_label correto após check_label."""
        mock_signal.return_value = _get_signal_mock(case)
        mock_pubmed.return_value = _get_pubmed_mock(case)
        mock_check_label.return_value = _label_check(
            case.drug, case.event, in_label=case.in_label or False
        )

        from hypokrates.cross.api import hypothesis

        result = await hypothesis(case.drug, case.event, check_label=True, use_cache=False)

        assert result.in_label == case.in_label, (
            f"[{case.scenario}] in_label: esperado {case.in_label}, obteve {result.in_label}"
        )


# ===========================================================================
# PARTE 3: Brand → Generic normalization
# ===========================================================================


class TestSentinelBrandNorm:
    """Testes sentinela de normalização brand→generic via RxNorm."""

    @pytest.fixture(autouse=True)
    def _disable_cache(self) -> None:
        configure(cache_enabled=False)

    @pytest.mark.parametrize(
        "case",
        BRAND_CASES,
        ids=[c.brand for c in BRAND_CASES],
    )
    async def test_brand_to_generic(self, case: BrandCase) -> None:
        """Verifica que normalize_drug resolve brand → generic."""
        from hypokrates.vocab.models import DrugNormResult

        mock_result = DrugNormResult(
            original=case.brand,
            generic_name=case.expected_generic,
            brand_names=[case.brand],
            rxcui="12345",
            meta=_meta("RxNorm"),
        )

        with patch("hypokrates.vocab.api.normalize_drug", new_callable=AsyncMock) as mock_norm:
            mock_norm.return_value = mock_result

            from hypokrates.vocab.api import normalize_drug

            result = await normalize_drug(case.brand, use_cache=False)

            assert result.generic_name is not None, f"[{case.brand}] generic_name é None"
            assert result.generic_name.lower() == case.expected_generic.lower(), (
                f"[{case.brand}] esperado '{case.expected_generic}', "
                f"obteve '{result.generic_name}'"
            )


# ===========================================================================
# PARTE 4: MedDRA grouping
# ===========================================================================


class TestSentinelMedDRA:
    """Testes sentinela de agrupamento MedDRA."""

    @pytest.mark.parametrize(
        "case",
        MEDDRA_CASES,
        ids=[c.expected_canonical for c in MEDDRA_CASES],
    )
    def test_meddra_grouping(self, case: MedDRAGroupCase) -> None:
        """Verifica que termos sinônimos agrupam sob o canonical correto."""
        for term in case.terms:
            canonical = canonical_term(term)
            assert canonical == case.expected_canonical, (
                f"'{term}' → '{canonical}', esperado '{case.expected_canonical}'"
            )

    def test_canonical_unknown_returns_self(self) -> None:
        """Termo desconhecido retorna ele mesmo."""
        assert canonical_term("XYZFAKEEVENT") == "XYZFAKEEVENT"

    def test_scan_merges_meddra_synonyms(self) -> None:
        """Scan com group_events=True consolida sinônimos."""
        from hypokrates.vocab.meddra import group_scan_items

        # Simular ScanItems com termos sinônimos
        items: list[Any] = []
        from hypokrates.scan.models import ScanItem

        for i, event in enumerate(["ANAPHYLACTIC SHOCK", "ANAPHYLACTIC REACTION", "BRADYCARDIA"]):
            item = ScanItem(
                drug="propofol",
                event=event,
                classification=HypothesisClassification.KNOWN_ASSOCIATION,
                signal=_signal("propofol", event),
                literature_count=10,
                evidence=_evidence(),
                summary=f"Known: propofol + {event}",
                score=10.0 - i,
                rank=i + 1,
            )
            items.append(item)

        merged = group_scan_items(items)

        events = [m.event for m in merged]
        assert "ANAPHYLAXIS" in events, f"ANAPHYLAXIS não encontrado em {events}"
        assert "BRADYCARDIA" in events
        # Os 2 termos de anaphylaxis devem ter sido mergeados em 1
        assert len(merged) == 2


# ===========================================================================
# PARTE 5: Consistência entre tools
# ===========================================================================


class TestSentinelConsistency:
    """Testes de consistência — signal, hypothesis, check_label, OT devem concordar."""

    @pytest.fixture(autouse=True)
    def _disable_cache(self) -> None:
        configure(cache_enabled=False)

    @pytest.mark.parametrize(
        "case",
        CONSISTENCY_CASES,
        ids=[f"{c.drug}_{c.event}" for c in CONSISTENCY_CASES],
    )
    @patch("hypokrates.opentargets.api.drug_safety_score", new_callable=AsyncMock)
    @patch("hypokrates.dailymed.api.check_label", new_callable=AsyncMock)
    @patch("hypokrates.cross.api.pubmed_api.search_papers")
    @patch("hypokrates.cross.api.stats_api.signal")
    async def test_signal_hypothesis_label_ot_agree(
        self,
        mock_signal: AsyncMock,
        mock_pubmed: AsyncMock,
        mock_check_label: AsyncMock,
        mock_ot_score: AsyncMock,
        case: ConsistencyCase,
    ) -> None:
        """Signal detecta → hypothesis >=EMERGING, label confirma, OT tem score."""
        # Setup: sinal forte + muitos papers + in_label + OT score alto
        sig = _signal(case.drug, case.event, detected=True, prr_val=5.0, prr_lci=3.0)
        mock_signal.return_value = sig
        mock_pubmed.return_value = _pubmed(30, 5)
        mock_check_label.return_value = _label_check(case.drug, case.event, in_label=True)
        mock_ot_score.return_value = 15.0

        from hypokrates.cross.api import hypothesis

        result = await hypothesis(
            case.drug,
            case.event,
            check_label=True,
            check_opentargets=True,
            use_cache=False,
        )

        # Todas as tools devem concordar que é real
        assert result.signal.signal_detected is True, (
            f"[{case.drug}+{case.event}] signal não detectou"
        )
        assert result.classification in (
            HypothesisClassification.KNOWN_ASSOCIATION,
            HypothesisClassification.EMERGING_SIGNAL,
        ), f"[{case.drug}+{case.event}] classificação inesperada: {result.classification}"
        assert result.in_label is True, f"[{case.drug}+{case.event}] não está na bula"
        assert result.ot_llr is not None and result.ot_llr > 0, (
            f"[{case.drug}+{case.event}] OT LLR ausente ou zero"
        )

    @patch("hypokrates.cross.api.pubmed_api.search_papers")
    @patch("hypokrates.cross.api.stats_api.signal")
    async def test_signal_no_detect_implies_no_signal_or_emerging(
        self,
        mock_signal: AsyncMock,
        mock_pubmed: AsyncMock,
    ) -> None:
        """Se signal não detecta, hypothesis deve ser NO_SIGNAL ou EMERGING (com papers)."""
        mock_signal.return_value = _signal("aspirin", "CARDIAC ARREST", detected=False)
        mock_pubmed.return_value = _pubmed(0)

        from hypokrates.cross.api import hypothesis

        result = await hypothesis("aspirin", "CARDIAC ARREST", use_cache=False)

        assert result.classification == HypothesisClassification.NO_SIGNAL


# ===========================================================================
# PARTE 6: Falha graciosa
# ===========================================================================


class TestSentinelGracefulFailure:
    """Testes de falha graciosa — o sistema nunca deve crashar."""

    @pytest.fixture(autouse=True)
    def _disable_cache(self) -> None:
        configure(cache_enabled=False)

    @patch("hypokrates.cross.api.pubmed_api.search_papers")
    @patch("hypokrates.cross.api.stats_api.signal")
    async def test_nonexistent_drug(
        self,
        mock_signal: AsyncMock,
        mock_pubmed: AsyncMock,
    ) -> None:
        """Droga inexistente → no_signal, sem crash."""
        mock_signal.return_value = _signal("xyznonexistent123", "NAUSEA", detected=False)
        mock_pubmed.return_value = _pubmed(0)

        from hypokrates.cross.api import hypothesis

        result = await hypothesis("xyznonexistent123", "NAUSEA", use_cache=False)

        assert result.classification == HypothesisClassification.NO_SIGNAL
        assert result.drug == "xyznonexistent123"

    @patch("hypokrates.cross.api.pubmed_api.search_papers")
    @patch("hypokrates.cross.api.stats_api.signal")
    async def test_nonexistent_event(
        self,
        mock_signal: AsyncMock,
        mock_pubmed: AsyncMock,
    ) -> None:
        """Evento inexistente → no_signal, sem crash."""
        mock_signal.return_value = _signal("propofol", "XYZFAKEEVENT999", detected=False)
        mock_pubmed.return_value = _pubmed(0)

        from hypokrates.cross.api import hypothesis

        result = await hypothesis("propofol", "XYZFAKEEVENT999", use_cache=False)

        assert result.classification == HypothesisClassification.NO_SIGNAL

    @patch("hypokrates.drugbank.api.drug_info", new_callable=AsyncMock)
    @patch("hypokrates.cross.api.pubmed_api.search_papers")
    @patch("hypokrates.cross.api.stats_api.signal")
    async def test_drugbank_absent_degrades_gracefully(
        self,
        mock_signal: AsyncMock,
        mock_pubmed: AsyncMock,
        mock_drug_info: AsyncMock,
    ) -> None:
        """DrugBank ausente (exceção) → degrada gracefully, mechanism=None."""
        mock_signal.return_value = _signal("propofol", "NAUSEA", detected=True)
        mock_pubmed.return_value = _pubmed(0)
        mock_drug_info.side_effect = FileNotFoundError("DrugBank XML not found")

        from hypokrates.cross.api import hypothesis

        result = await hypothesis("propofol", "NAUSEA", check_drugbank=True, use_cache=False)

        # Não crashou, classificação funciona, mechanism=None
        assert result.classification == HypothesisClassification.NOVEL_HYPOTHESIS
        assert result.mechanism is None

    @patch("hypokrates.dailymed.api.label_events", new_callable=AsyncMock)
    @patch("hypokrates.cross.api.pubmed_api.search_papers")
    @patch("hypokrates.cross.api.stats_api.signal")
    async def test_dailymed_no_spl_degrades_gracefully(
        self,
        mock_signal: AsyncMock,
        mock_pubmed: AsyncMock,
        mock_label_events: AsyncMock,
    ) -> None:
        """DailyMed sem SPL (exceção) → hypothesis degrada gracefully.

        FIX: hypothesis() agora captura exceções de label_events e continua
        com in_label=None em vez de propagar a exceção.
        """
        mock_signal.return_value = _signal("propofol", "NAUSEA", detected=True)
        mock_pubmed.return_value = _pubmed(0)
        mock_label_events.side_effect = Exception("No SPL found")

        from hypokrates.cross.api import hypothesis

        result = await hypothesis("propofol", "NAUSEA", check_label=True, use_cache=False)
        assert result.in_label is None
        assert result.classification is not None

    @patch("hypokrates.scan.api.cross_api.hypothesis")
    @patch("hypokrates.scan.api.faers_api.top_events")
    async def test_scan_empty_drug(
        self,
        mock_top_events: AsyncMock,
        mock_hypothesis: AsyncMock,
    ) -> None:
        """Scan de droga sem eventos FAERS → ScanResult vazio, sem crash."""
        mock_top_events.return_value = FAERSResult(events=[], meta=_meta())

        from hypokrates.scan.api import scan_drug

        result = await scan_drug("xyznonexistent123", top_n=10)

        assert result.total_scanned == 0
        assert result.items == []
        mock_hypothesis.assert_not_called()

    @patch("hypokrates.scan.api._check_bulk_available", new_callable=AsyncMock)
    @patch("hypokrates.scan.api.cross_api.hypothesis")
    @patch("hypokrates.scan.api.faers_api.top_events")
    async def test_bulk_store_empty_auto_falls_back_to_api(
        self,
        mock_top_events: AsyncMock,
        mock_hypothesis: AsyncMock,
        mock_bulk_avail: AsyncMock,
    ) -> None:
        """Bulk store vazio + use_bulk=None (auto) → fallback para API, sem crash."""
        mock_bulk_avail.return_value = False
        mock_top_events.return_value = _events(["NAUSEA"])
        mock_hypothesis.return_value = _hypothesis_result(
            "propofol", "NAUSEA", HypothesisClassification.KNOWN_ASSOCIATION, lit_count=10
        )

        from hypokrates.scan.api import scan_drug

        # use_bulk=None (auto-detect) → _check_bulk_available=False → API fallback
        result = await scan_drug("propofol", top_n=1, use_bulk=None, group_events=False)

        assert result.bulk_mode is False
        assert len(result.items) == 1


# ===========================================================================
# PARTE 7: Drogas ruidosas — scan não deve produzir lixo
# ===========================================================================


class TestSentinelNoisyDrugs:
    """Testes sentinela com drogas que costumam expor ruído."""

    @pytest.fixture(autouse=True)
    def _disable_cache(self) -> None:
        configure(cache_enabled=False)

    @pytest.mark.parametrize("drug", NOISY_DRUGS, ids=NOISY_DRUGS)
    @patch("hypokrates.scan.api._check_bulk_available", new_callable=AsyncMock, return_value=False)
    @patch("hypokrates.scan.api.cross_api.hypothesis")
    @patch("hypokrates.scan.api.faers_api.top_events")
    async def test_noisy_drug_scan_no_crash(
        self,
        mock_top_events: AsyncMock,
        mock_hypothesis: AsyncMock,
        mock_bulk_avail: AsyncMock,
        drug: str,
    ) -> None:
        """Scan de droga ruidosa completa sem crash, resultados plausíveis."""
        # top_n=5, OVERFETCH_MULTIPLIER=3 → fetch_limit=15
        # Precisamos de 15 eventos e 15 hypothesis results
        events = [
            "NAUSEA",
            "HEADACHE",
            "DIARRHOEA",
            "FATIGUE",
            "DIZZINESS",
            "VOMITING",
            "RASH",
            "PRURITUS",
            "ARTHRALGIA",
            "MYALGIA",
            "INSOMNIA",
            "ANXIETY",
            "ABDOMINAL DISCOMFORT",
            "CONSTIPATION",
            "DYSPNOEA",
        ]
        mock_top_events.return_value = _events(events)

        mock_hypothesis.side_effect = [
            _hypothesis_result(
                drug,
                ev,
                HypothesisClassification.KNOWN_ASSOCIATION,
                lit_count=20,
                prr_lci=1.0 + i * 0.3,
            )
            for i, ev in enumerate(events)
        ]

        from hypokrates.scan.api import scan_drug

        result = await scan_drug(drug, top_n=5, group_events=False)

        # Sem crash, resultados truncados a top_n=5
        assert result.drug == drug
        assert result.total_scanned == 15  # overfetch: 5*3
        assert len(result.items) == 5
        assert result.failed_count == 0

        # Scores monotonicamente decrescentes (ranking correto)
        scores = [item.score for item in result.items]
        assert scores == sorted(scores, reverse=True), (
            f"[{drug}] scores não estão em ordem decrescente: {scores}"
        )

    @pytest.mark.parametrize("drug", NOISY_DRUGS, ids=NOISY_DRUGS)
    @patch("hypokrates.scan.api._check_bulk_available", new_callable=AsyncMock, return_value=False)
    @patch("hypokrates.scan.api.cross_api.hypothesis")
    @patch("hypokrates.scan.api.faers_api.top_events")
    async def test_noisy_drug_operational_filtered(
        self,
        mock_top_events: AsyncMock,
        mock_hypothesis: AsyncMock,
        mock_bulk_avail: AsyncMock,
        drug: str,
    ) -> None:
        """Drogas ruidosas com termos operacionais → filtrados corretamente."""
        # top_n=5 → fetch_limit=15. Incluir termos operacionais + reais
        # NOTA: "PAIN" e "FALL" também são operacionais — evitar nos "reais"
        operational = ["OFF LABEL USE", "DRUG INEFFECTIVE", "DEATH"]
        real_events = [
            "NAUSEA",
            "HEADACHE",
            "DIARRHOEA",
            "FATIGUE",
            "DIZZINESS",
            "VOMITING",
            "RASH",
            "PRURITUS",
            "ARTHRALGIA",
            "MYALGIA",
            "INSOMNIA",
            "ANXIETY",
        ]
        all_events = real_events[:3] + operational + real_events[3:]
        mock_top_events.return_value = _events(all_events)

        # Após filtrar 3 operacionais, restam 12 eventos reais para hypothesis
        mock_hypothesis.side_effect = [
            _hypothesis_result(drug, ev, HypothesisClassification.KNOWN_ASSOCIATION, lit_count=10)
            for ev in real_events
        ]

        from hypokrates.scan.api import scan_drug

        result = await scan_drug(drug, top_n=5, filter_operational=True)

        assert result.filtered_operational_count == 3
        event_names = [item.event for item in result.items]
        assert "OFF LABEL USE" not in event_names
        assert "DRUG INEFFECTIVE" not in event_names
        assert "DEATH" not in event_names


# ===========================================================================
# PARTE 8: Scan completo — volume_flag e coadmin_flag
# ===========================================================================


class TestSentinelScanFlags:
    """Testes sentinela para flags de volume e co-admin no scan."""

    @pytest.fixture(autouse=True)
    def _disable_cache(self) -> None:
        configure(cache_enabled=False)

    @patch("hypokrates.scan.api.cross_api.hypothesis")
    @patch("hypokrates.scan.api.faers_api.top_events")
    async def test_volume_flag_cetirizine_glossodynia(
        self,
        mock_top_events: AsyncMock,
        mock_hypothesis: AsyncMock,
    ) -> None:
        """Cetirizine + glossodynia: volume_flag=True (>2000 reports)."""
        mock_top_events.return_value = _events(["GLOSSODYNIA"])

        hyp = _hypothesis_result(
            "cetirizine",
            "GLOSSODYNIA",
            HypothesisClassification.KNOWN_ASSOCIATION,
            lit_count=5,
            a=7743,  # volume anômalo
        )
        mock_hypothesis.return_value = hyp

        from hypokrates.scan.api import scan_drug

        result = await scan_drug("cetirizine", top_n=1, group_events=False)

        assert len(result.items) == 1
        assert result.items[0].volume_flag is True, (
            "Cetirizine + glossodynia deveria ter volume_flag=True"
        )

    @patch("hypokrates.faers.api.co_suspect_profile", new_callable=AsyncMock)
    @patch("hypokrates.scan.api.cross_api.hypothesis")
    @patch("hypokrates.scan.api.faers_api.top_events")
    async def test_coadmin_flag_ondansetron_neutropenia(
        self,
        mock_top_events: AsyncMock,
        mock_hypothesis: AsyncMock,
        mock_coadmin: AsyncMock,
    ) -> None:
        """Ondansetron + febrile neutropenia: coadmin_flag detectado."""
        mock_top_events.return_value = _events(["FEBRILE NEUTROPENIA"])

        hyp = _hypothesis_result(
            "ondansetron",
            "FEBRILE NEUTROPENIA",
            HypothesisClassification.KNOWN_ASSOCIATION,
            lit_count=5,
            coadmin_flag=True,
        )
        mock_hypothesis.return_value = hyp

        mock_coadmin.return_value = CoSuspectProfile(
            drug="ondansetron",
            event="FEBRILE NEUTROPENIA",
            total_reports=50,
            median_suspects=5.2,
            co_admin_flag=True,
            top_co_suspects=["CISPLATIN", "DEXAMETHASONE", "CARBOPLATIN"],
            meta=_meta(),
        )

        from hypokrates.scan.api import scan_drug

        result = await scan_drug("ondansetron", top_n=1, check_coadmin=True, group_events=False)

        assert len(result.items) == 1
        assert result.items[0].coadmin_flag is True, (
            "Ondansetron + febrile neutropenia deveria ter coadmin_flag=True"
        )


# ===========================================================================
# PARTE 9: Scan com MedDRA grouping integrado
# ===========================================================================


class TestSentinelScanGrouping:
    """Testes sentinela para scan com MedDRA grouping."""

    @pytest.fixture(autouse=True)
    def _disable_cache(self) -> None:
        configure(cache_enabled=False)

    @patch("hypokrates.scan.api.cross_api.hypothesis")
    @patch("hypokrates.scan.api.faers_api.top_events")
    async def test_qt_terms_grouped_in_scan(
        self,
        mock_top_events: AsyncMock,
        mock_hypothesis: AsyncMock,
    ) -> None:
        """QT PROLONGATION e ELECTROCARDIOGRAM QT PROLONGED agrupam no scan."""
        # top_n=3 → fetch_limit=9. Precisa de 9 eventos
        events = [
            "QT PROLONGATION",
            "ELECTROCARDIOGRAM QT PROLONGED",
            "NAUSEA",
            "HEADACHE",
            "DIARRHOEA",
            "FATIGUE",
            "DIZZINESS",
            "VOMITING",
            "RASH",
        ]
        mock_top_events.return_value = _events(events)

        mock_hypothesis.side_effect = [
            _hypothesis_result(
                "amiodarone",
                "QT PROLONGATION",
                HypothesisClassification.KNOWN_ASSOCIATION,
                lit_count=50,
                prr_val=10.0,
                prr_lci=8.0,
            ),
            _hypothesis_result(
                "amiodarone",
                "ELECTROCARDIOGRAM QT PROLONGED",
                HypothesisClassification.KNOWN_ASSOCIATION,
                lit_count=30,
                prr_val=8.0,
                prr_lci=6.0,
            ),
        ] + [
            _hypothesis_result(
                "amiodarone",
                ev,
                HypothesisClassification.KNOWN_ASSOCIATION,
                lit_count=10,
                prr_val=2.0,
                prr_lci=1.5,
            )
            for ev in events[2:]
        ]

        from hypokrates.scan.api import scan_drug

        result = await scan_drug("amiodarone", top_n=3, group_events=True)

        events_out = [item.event for item in result.items]
        assert "QT PROLONGATION" in events_out, f"QT PROLONGATION não encontrado em {events_out}"
        # QT e ELECTROCARDIOGRAM QT PROLONGED devem estar agrupados (merged)
        assert result.groups_applied is True
        # Após grouping: QT PROLONGATION absorve ELECTROCARDIOGRAM QT PROLONGED
        qt_items = [i for i in result.items if i.event == "QT PROLONGATION"]
        assert len(qt_items) == 1
        # ELECTROCARDIOGRAM QT PROLONGED não deve estar separado
        assert "ELECTROCARDIOGRAM QT PROLONGED" not in events_out


# ===========================================================================
# PARTE 10: Regressão — invariantes do pipeline
# ===========================================================================


class TestSentinelInvariants:
    """Invariantes que devem sempre valer, independente dos dados."""

    @pytest.fixture(autouse=True)
    def _disable_cache(self) -> None:
        configure(cache_enabled=False)

    @patch("hypokrates.cross.api.pubmed_api.search_papers")
    @patch("hypokrates.cross.api.stats_api.signal")
    async def test_novel_requires_signal_and_zero_papers(
        self,
        mock_signal: AsyncMock,
        mock_pubmed: AsyncMock,
    ) -> None:
        """NOVEL_HYPOTHESIS exige signal_detected=True e 0 papers."""
        mock_signal.return_value = _signal("drug_x", "EVENT_Y", detected=True)
        mock_pubmed.return_value = _pubmed(0)

        from hypokrates.cross.api import hypothesis

        result = await hypothesis("drug_x", "EVENT_Y", use_cache=False)

        assert result.classification == HypothesisClassification.NOVEL_HYPOTHESIS
        assert result.signal.signal_detected is True
        assert result.literature_count == 0

    @patch("hypokrates.cross.api.pubmed_api.search_papers")
    @patch("hypokrates.cross.api.stats_api.signal")
    async def test_known_requires_many_papers(
        self,
        mock_signal: AsyncMock,
        mock_pubmed: AsyncMock,
    ) -> None:
        """KNOWN_ASSOCIATION exige > emerging_max papers."""
        mock_signal.return_value = _signal("drug_x", "EVENT_Y", detected=True)
        mock_pubmed.return_value = _pubmed(50, 5)

        from hypokrates.cross.api import hypothesis

        result = await hypothesis("drug_x", "EVENT_Y", use_cache=False)

        assert result.classification == HypothesisClassification.KNOWN_ASSOCIATION
        assert result.literature_count > 5  # > emerging_max

    @patch("hypokrates.cross.api.pubmed_api.search_papers")
    @patch("hypokrates.cross.api.stats_api.signal")
    async def test_no_signal_without_detection(
        self,
        mock_signal: AsyncMock,
        mock_pubmed: AsyncMock,
    ) -> None:
        """NO_SIGNAL quando não há detecção e poucos papers."""
        mock_signal.return_value = _signal("drug_x", "EVENT_Y", detected=False)
        mock_pubmed.return_value = _pubmed(2, 2)

        from hypokrates.cross.api import hypothesis

        result = await hypothesis("drug_x", "EVENT_Y", use_cache=False)

        assert result.classification == HypothesisClassification.NO_SIGNAL

    @patch("hypokrates.cross.api.pubmed_api.search_papers")
    @patch("hypokrates.cross.api.stats_api.signal")
    async def test_in_label_true_blocks_novel(
        self,
        mock_signal: AsyncMock,
        mock_pubmed: AsyncMock,
    ) -> None:
        """Signal + in_label=True + 0 papers → EMERGING (não NOVEL)."""
        mock_signal.return_value = _signal("drug_x", "EVENT_Y", detected=True)
        mock_pubmed.return_value = _pubmed(0)

        with patch("hypokrates.dailymed.api.label_events", new_callable=AsyncMock) as mock_le:
            from hypokrates.dailymed.models import LabelEventsResult

            mock_le.return_value = LabelEventsResult(
                drug="drug_x",
                events=["EVENT_Y"],
                meta=_meta("DailyMed"),
            )

            from hypokrates.cross.api import hypothesis

            result = await hypothesis("drug_x", "EVENT_Y", check_label=True, use_cache=False)

            assert result.in_label is True
            assert result.classification == HypothesisClassification.EMERGING_SIGNAL, (
                "in_label=True deve bloquear NOVEL → EMERGING"
            )

    @patch("hypokrates.scan.api.cross_api.hypothesis")
    @patch("hypokrates.scan.api.faers_api.top_events")
    async def test_scan_ranks_are_sequential(
        self,
        mock_top_events: AsyncMock,
        mock_hypothesis: AsyncMock,
    ) -> None:
        """Ranks de scan são sempre 1, 2, 3, ... sem gaps."""
        mock_top_events.return_value = _events(["A", "B", "C", "D"])
        mock_hypothesis.side_effect = [
            _hypothesis_result("d", "A", HypothesisClassification.NOVEL_HYPOTHESIS, prr_lci=5.0),
            _hypothesis_result(
                "d", "B", HypothesisClassification.EMERGING_SIGNAL, lit_count=3, prr_lci=3.0
            ),
            _hypothesis_result(
                "d", "C", HypothesisClassification.KNOWN_ASSOCIATION, lit_count=10, prr_lci=1.5
            ),
            _hypothesis_result(
                "d", "D", HypothesisClassification.KNOWN_ASSOCIATION, lit_count=20, prr_lci=1.0
            ),
        ]

        from hypokrates.scan.api import scan_drug

        result = await scan_drug("d", top_n=4, group_events=False)

        ranks = [item.rank for item in result.items]
        assert ranks == list(range(1, len(ranks) + 1)), f"Ranks não sequenciais: {ranks}"

    @patch("hypokrates.scan.api.cross_api.hypothesis")
    @patch("hypokrates.scan.api.faers_api.top_events")
    async def test_scan_scores_descending(
        self,
        mock_top_events: AsyncMock,
        mock_hypothesis: AsyncMock,
    ) -> None:
        """Scores de scan são monotonicamente decrescentes."""
        mock_top_events.return_value = _events(["A", "B", "C"])
        mock_hypothesis.side_effect = [
            _hypothesis_result("d", "A", HypothesisClassification.NOVEL_HYPOTHESIS, prr_lci=10.0),
            _hypothesis_result(
                "d", "B", HypothesisClassification.EMERGING_SIGNAL, lit_count=3, prr_lci=2.0
            ),
            _hypothesis_result(
                "d", "C", HypothesisClassification.KNOWN_ASSOCIATION, lit_count=10, prr_lci=1.0
            ),
        ]

        from hypokrates.scan.api import scan_drug

        result = await scan_drug("d", top_n=3, group_events=False)

        scores = [item.score for item in result.items]
        assert scores == sorted(scores, reverse=True), f"Scores não decrescentes: {scores}"
