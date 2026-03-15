"""Testes para hypokrates.mcp.tools — todas as tools MCP.

Usa um ToolCapture mock para capturar as funções registradas sem
depender do servidor MCP real.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from typing import Any
from unittest.mock import AsyncMock, patch

from hypokrates.constants import __version__
from hypokrates.cross.models import HypothesisClassification, HypothesisResult
from hypokrates.evidence.models import EvidenceBlock
from hypokrates.faers.models import (
    FAERSReaction,
    FAERSReport,
    FAERSResult,
)
from hypokrates.models import AdverseEvent, MetaInfo
from hypokrates.pubmed.models import PubMedArticle, PubMedSearchResult
from hypokrates.scan.models import ScanItem, ScanResult
from hypokrates.stats.models import ContingencyTable, DisproportionalityResult, SignalResult
from hypokrates.vocab.models import DrugNormResult, MeSHResult

# ---------------------------------------------------------------------------
# ToolCapture — mock do FastMCP para capturar funções registradas
# ---------------------------------------------------------------------------


class ToolCapture:
    """Captura tools registradas via @mcp.tool()."""

    def __init__(self) -> None:
        self.tools: dict[str, Any] = {}

    def tool(self) -> Any:
        def decorator(fn: Any) -> Any:
            self.tools[fn.__name__] = fn
            return fn

        return decorator


# ---------------------------------------------------------------------------
# Fixtures de dados de teste
# ---------------------------------------------------------------------------


def _make_meta(source: str = "test", total: int = 0) -> MetaInfo:
    return MetaInfo(
        source=source,
        query={"test": True},
        total_results=total,
        retrieved_at=datetime.now(UTC),
    )


def _make_signal(
    drug: str = "propofol",
    event: str = "HYPOTENSION",
    *,
    detected: bool = True,
    a: int = 100,
) -> SignalResult:
    return SignalResult(
        drug=drug,
        event=event,
        table=ContingencyTable(a=a, b=900, c=50, d=9000),
        prr=DisproportionalityResult(
            measure="PRR", value=2.0, ci_lower=1.5, ci_upper=2.5, significant=True
        ),
        ror=DisproportionalityResult(
            measure="ROR", value=2.2, ci_lower=1.6, ci_upper=2.8, significant=True
        ),
        ic=DisproportionalityResult(
            measure="IC", value=1.0, ci_lower=0.5, ci_upper=1.5, significant=True
        ),
        signal_detected=detected,
        meta=_make_meta("OpenFDA/FAERS"),
    )


def _make_evidence() -> EvidenceBlock:
    return EvidenceBlock(
        source="OpenFDA/FAERS",
        retrieved_at=datetime.now(UTC),
        data={"drug": "propofol"},
    )


def _make_article(pmid: str = "12345", title: str = "Test Article") -> PubMedArticle:
    return PubMedArticle(pmid=pmid, title=title)


# ---------------------------------------------------------------------------
# Tests: FAERS tools
# ---------------------------------------------------------------------------


class TestFAERSTools:
    """MCP tools para FAERS."""

    async def test_adverse_events(self) -> None:
        from hypokrates.mcp.tools import faers

        capture = ToolCapture()
        faers.register(capture)  # type: ignore[arg-type]

        mock_result = FAERSResult(
            reports=[
                FAERSReport(
                    safety_report_id="RPT001",
                    reactions=[FAERSReaction(term="NAUSEA"), FAERSReaction(term="VOMITING")],
                )
            ],
            meta=_make_meta("OpenFDA/FAERS", total=100),
        )

        with patch.object(faers, "faers_api") as mock_api:
            mock_api.adverse_events = AsyncMock(return_value=mock_result)
            result = await capture.tools["adverse_events"]("propofol")

        parsed = json.loads(result)
        assert parsed["drug"] == "propofol"
        assert parsed["total"] == 100
        assert len(parsed["reports"]) == 1
        assert parsed["reports"][0]["id"] == "RPT001"
        assert "NAUSEA" in parsed["reports"][0]["reactions"]

    async def test_top_events(self) -> None:
        from hypokrates.mcp.tools import faers

        capture = ToolCapture()
        faers.register(capture)  # type: ignore[arg-type]

        mock_result = FAERSResult(
            events=[
                AdverseEvent(term="NAUSEA", count=500),
                AdverseEvent(term="HEADACHE", count=300),
            ],
            meta=_make_meta("OpenFDA/FAERS"),
        )

        with patch.object(faers, "faers_api") as mock_api:
            mock_api.top_events = AsyncMock(return_value=mock_result)
            result = await capture.tools["top_events"]("propofol")

        assert "PROPOFOL" in result
        assert "NAUSEA" in result
        assert "500 reports" in result
        assert "HEADACHE" in result

    async def test_compare_drugs(self) -> None:
        from hypokrates.mcp.tools import faers

        capture = ToolCapture()
        faers.register(capture)  # type: ignore[arg-type]

        mock_results = {
            "propofol": FAERSResult(
                events=[AdverseEvent(term="NAUSEA", count=100)],
                meta=_make_meta(),
            ),
            "ketamine": FAERSResult(
                events=[AdverseEvent(term="HALLUCINATION", count=50)],
                meta=_make_meta(),
            ),
        }

        with patch.object(faers, "faers_api") as mock_api:
            mock_api.compare = AsyncMock(return_value=mock_results)
            result = await capture.tools["compare_drugs"]("propofol,ketamine")

        assert "PROPOFOL" in result
        assert "KETAMINE" in result
        assert "NAUSEA" in result
        assert "HALLUCINATION" in result


# ---------------------------------------------------------------------------
# Tests: Stats tools
# ---------------------------------------------------------------------------


class TestStatsTools:
    """MCP tools para signal detection."""

    async def test_signal(self) -> None:
        from hypokrates.mcp.tools import stats

        capture = ToolCapture()
        stats.register(capture)  # type: ignore[arg-type]

        mock_result = _make_signal()

        with patch.object(stats, "stats_api") as mock_api:
            mock_api.signal = AsyncMock(return_value=mock_result)
            result = await capture.tools["signal"]("propofol", "HYPOTENSION")

        assert "PROPOFOL" in result
        assert "HYPOTENSION" in result
        assert "Signal detected:** YES" in result
        assert "PRR" in result
        assert "ROR" in result
        assert "drug+event: 100" in result

    async def test_signal_not_detected(self) -> None:
        from hypokrates.mcp.tools import stats

        capture = ToolCapture()
        stats.register(capture)  # type: ignore[arg-type]

        mock_result = _make_signal(detected=False)

        with patch.object(stats, "stats_api") as mock_api:
            mock_api.signal = AsyncMock(return_value=mock_result)
            result = await capture.tools["signal"]("aspirin", "HEADACHE")

        assert "Signal detected:** NO" in result


# ---------------------------------------------------------------------------
# Tests: PubMed tools
# ---------------------------------------------------------------------------


class TestPubMedTools:
    """MCP tools para PubMed."""

    async def test_count_papers(self) -> None:
        from hypokrates.mcp.tools import pubmed

        capture = ToolCapture()
        pubmed.register(capture)  # type: ignore[arg-type]

        mock_result = PubMedSearchResult(
            total_count=42,
            meta=_make_meta("PubMed"),
        )

        with patch.object(pubmed, "pubmed_api") as mock_api:
            mock_api.count_papers = AsyncMock(return_value=mock_result)
            result = await capture.tools["count_papers"]("propofol", "hepatotoxicity")

        assert "propofol" in result
        assert "hepatotoxicity" in result
        assert "42" in result

    async def test_search_papers(self) -> None:
        from hypokrates.mcp.tools import pubmed

        capture = ToolCapture()
        pubmed.register(capture)  # type: ignore[arg-type]

        mock_result = PubMedSearchResult(
            total_count=1,
            articles=[
                PubMedArticle(
                    pmid="38901234",
                    title="Propofol hepatotoxicity review",
                    doi="10.1234/test",
                )
            ],
            meta=_make_meta("PubMed"),
        )

        with patch.object(pubmed, "pubmed_api") as mock_api:
            mock_api.search_papers = AsyncMock(return_value=mock_result)
            result = await capture.tools["search_papers"]("propofol", "hepatotoxicity")

        assert "38901234" in result
        assert "Propofol hepatotoxicity review" in result
        assert "doi:10.1234/test" in result

    async def test_search_papers_no_doi(self) -> None:
        from hypokrates.mcp.tools import pubmed

        capture = ToolCapture()
        pubmed.register(capture)  # type: ignore[arg-type]

        mock_result = PubMedSearchResult(
            total_count=1,
            articles=[PubMedArticle(pmid="111", title="No DOI article")],
            meta=_make_meta("PubMed"),
        )

        with patch.object(pubmed, "pubmed_api") as mock_api:
            mock_api.search_papers = AsyncMock(return_value=mock_result)
            result = await capture.tools["search_papers"]("drug", "event")

        assert "No DOI article" in result
        assert "doi:" not in result


# ---------------------------------------------------------------------------
# Tests: Cross tools
# ---------------------------------------------------------------------------


class TestCrossTools:
    """MCP tools para cross-reference."""

    async def test_hypothesis_with_articles(self) -> None:
        from hypokrates.mcp.tools import cross

        capture = ToolCapture()
        cross.register(capture)  # type: ignore[arg-type]

        mock_result = HypothesisResult(
            drug="propofol",
            event="PRIS",
            classification=HypothesisClassification.EMERGING_SIGNAL,
            signal=_make_signal("propofol", "PRIS"),
            literature_count=3,
            articles=[_make_article("111", "PRIS case report")],
            evidence=_make_evidence(),
            summary="Emerging signal for propofol-PRIS.",
        )

        with patch.object(cross, "cross_api") as mock_api:
            mock_api.hypothesis = AsyncMock(return_value=mock_result)
            result = await capture.tools["hypothesis"]("propofol", "PRIS")

        assert "PROPOFOL" in result
        assert "PRIS" in result
        assert "emerging_signal" in result
        assert "Literature count:** 3" in result
        assert "PRIS case report" in result

    async def test_hypothesis_no_articles(self) -> None:
        from hypokrates.mcp.tools import cross

        capture = ToolCapture()
        cross.register(capture)  # type: ignore[arg-type]

        mock_result = HypothesisResult(
            drug="propofol",
            event="RASH",
            classification=HypothesisClassification.NOVEL_HYPOTHESIS,
            signal=_make_signal("propofol", "RASH"),
            literature_count=0,
            articles=[],
            evidence=_make_evidence(),
            summary="Novel hypothesis.",
        )

        with patch.object(cross, "cross_api") as mock_api:
            mock_api.hypothesis = AsyncMock(return_value=mock_result)
            result = await capture.tools["hypothesis"]("propofol", "RASH")

        assert "novel_hypothesis" in result
        assert "Articles" not in result


# ---------------------------------------------------------------------------
# Tests: Scan tools
# ---------------------------------------------------------------------------


class TestScanTools:
    """MCP tools para scan."""

    async def test_scan_drug_with_results(self) -> None:
        from hypokrates.mcp.tools import scan

        capture = ToolCapture()
        scan.register(capture)  # type: ignore[arg-type]

        signal = _make_signal()
        mock_result = ScanResult(
            drug="propofol",
            items=[
                ScanItem(
                    drug="propofol",
                    event="HYPOTENSION",
                    classification=HypothesisClassification.KNOWN_ASSOCIATION,
                    signal=signal,
                    literature_count=50,
                    evidence=_make_evidence(),
                    summary="Known.",
                    score=4.5,
                    rank=1,
                ),
            ],
            total_scanned=1,
            novel_count=0,
            emerging_count=0,
            known_count=1,
            no_signal_count=0,
            meta=_make_meta(),
        )

        with patch.object(scan, "scan_api") as mock_api:
            mock_api.scan_drug = AsyncMock(return_value=mock_result)
            result = await capture.tools["scan_drug"]("propofol", 5)

        assert "PROPOFOL" in result
        assert "HYPOTENSION" in result
        assert "known_association" in result
        assert "1 novel" in result or "0 novel" in result
        assert "1 known" in result

    async def test_scan_drug_with_failures(self) -> None:
        from hypokrates.mcp.tools import scan

        capture = ToolCapture()
        scan.register(capture)  # type: ignore[arg-type]

        mock_result = ScanResult(
            drug="propofol",
            items=[],
            total_scanned=3,
            failed_count=2,
            skipped_events=["EVENT_A", "EVENT_B"],
            meta=_make_meta(),
        )

        with patch.object(scan, "scan_api") as mock_api:
            mock_api.scan_drug = AsyncMock(return_value=mock_result)
            result = await capture.tools["scan_drug"]("propofol", 3)

        assert "2 failed" in result
        assert "EVENT_A" in result
        assert "EVENT_B" in result

    async def test_scan_drug_clamps_top_n(self) -> None:
        """top_n > 20 é clamped para 20."""
        from hypokrates.mcp.tools import scan

        capture = ToolCapture()
        scan.register(capture)  # type: ignore[arg-type]

        mock_result = ScanResult(
            drug="propofol",
            items=[],
            total_scanned=0,
            meta=_make_meta(),
        )

        with patch.object(scan, "scan_api") as mock_api:
            mock_api.scan_drug = AsyncMock(return_value=mock_result)
            await capture.tools["scan_drug"]("propofol", 50)
            call_kwargs = mock_api.scan_drug.call_args
            assert call_kwargs[1]["top_n"] == 20


# ---------------------------------------------------------------------------
# Tests: Vocab tools
# ---------------------------------------------------------------------------


class TestVocabTools:
    """MCP tools para normalização de vocabulário."""

    async def test_normalize_drug_found(self) -> None:
        from hypokrates.mcp.tools import vocab

        capture = ToolCapture()
        vocab.register(capture)  # type: ignore[arg-type]

        mock_result = DrugNormResult(
            original="advil",
            generic_name="ibuprofen",
            brand_names=["Advil", "Motrin"],
            rxcui="5640",
            meta=_make_meta("RxNorm"),
        )

        with patch.object(vocab, "vocab_api") as mock_api:
            mock_api.normalize_drug = AsyncMock(return_value=mock_result)
            result = await capture.tools["normalize_drug"]("advil")

        assert "ibuprofen" in result
        assert "5640" in result
        assert "Advil" in result
        assert "Motrin" in result

    async def test_normalize_drug_not_found(self) -> None:
        from hypokrates.mcp.tools import vocab

        capture = ToolCapture()
        vocab.register(capture)  # type: ignore[arg-type]

        mock_result = DrugNormResult(
            original="xyz123",
            meta=_make_meta("RxNorm"),
        )

        with patch.object(vocab, "vocab_api") as mock_api:
            mock_api.normalize_drug = AsyncMock(return_value=mock_result)
            result = await capture.tools["normalize_drug"]("xyz123")

        assert "No match found" in result

    async def test_map_to_mesh_found(self) -> None:
        from hypokrates.mcp.tools import vocab

        capture = ToolCapture()
        vocab.register(capture)  # type: ignore[arg-type]

        mock_result = MeSHResult(
            query="aspirin",
            mesh_id="D001241",
            mesh_term="Aspirin",
            tree_numbers=["D02.455", "D09.698"],
            meta=_make_meta("NCBI/MeSH"),
        )

        with patch.object(vocab, "vocab_api") as mock_api:
            mock_api.map_to_mesh = AsyncMock(return_value=mock_result)
            result = await capture.tools["map_to_mesh"]("aspirin")

        assert "Aspirin" in result
        assert "D001241" in result
        assert "D02.455" in result

    async def test_map_to_mesh_not_found(self) -> None:
        from hypokrates.mcp.tools import vocab

        capture = ToolCapture()
        vocab.register(capture)  # type: ignore[arg-type]

        mock_result = MeSHResult(
            query="xyz123",
            meta=_make_meta("NCBI/MeSH"),
        )

        with patch.object(vocab, "vocab_api") as mock_api:
            mock_api.map_to_mesh = AsyncMock(return_value=mock_result)
            result = await capture.tools["map_to_mesh"]("xyz123")

        assert "No MeSH match found" in result


# ---------------------------------------------------------------------------
# Tests: Meta tools
# ---------------------------------------------------------------------------


class TestMetaTools:
    """MCP tools de metadados."""

    async def test_list_tools(self) -> None:
        from hypokrates.mcp.tools import meta

        capture = ToolCapture()
        meta.register(capture)  # type: ignore[arg-type]

        result = await capture.tools["list_tools"]()

        assert f"{len(meta._TOOLS)} tools" in result
        assert "adverse_events" in result
        assert "scan_drug" in result
        assert "normalize_drug" in result
        assert "label_events" in result
        assert "search_trials" in result
        assert "drug_info" in result
        assert "drug_adverse_events" in result
        assert "drug_mechanism" in result
        assert "version" in result

    async def test_version(self) -> None:
        from hypokrates.mcp.tools import meta

        capture = ToolCapture()
        meta.register(capture)  # type: ignore[arg-type]

        result = await capture.tools["version"]()

        assert __version__ in result
        assert "Sprint" in result
        assert str(len(meta._TOOLS)) in result


# ---------------------------------------------------------------------------
# Tests: DailyMed tools
# ---------------------------------------------------------------------------


class TestDailyMedTools:
    """MCP tools para DailyMed (bulas FDA)."""

    async def test_label_events_found(self) -> None:
        from hypokrates.dailymed.models import LabelEventsResult
        from hypokrates.mcp.tools import dailymed

        capture = ToolCapture()
        dailymed.register(capture)  # type: ignore[arg-type]

        mock_result = LabelEventsResult(
            drug="propofol",
            set_id="abc-123",
            events=["BRADYCARDIA", "HYPOTENSION", "APNEA"],
            meta=_make_meta("DailyMed"),
        )

        with patch.object(dailymed, "dailymed_api") as mock_api:
            mock_api.label_events = AsyncMock(return_value=mock_result)
            result = await capture.tools["label_events"]("propofol")

        assert "PROPOFOL" in result
        assert "abc-123" in result
        assert "BRADYCARDIA" in result
        assert "3" in result  # events found count

    async def test_label_events_empty(self) -> None:
        from hypokrates.dailymed.models import LabelEventsResult
        from hypokrates.mcp.tools import dailymed

        capture = ToolCapture()
        dailymed.register(capture)  # type: ignore[arg-type]

        mock_result = LabelEventsResult(
            drug="unknowndrug",
            events=[],
            meta=_make_meta("DailyMed"),
        )

        with patch.object(dailymed, "dailymed_api") as mock_api:
            mock_api.label_events = AsyncMock(return_value=mock_result)
            result = await capture.tools["label_events"]("unknowndrug")

        assert "No adverse reactions section found" in result

    async def test_check_label_found(self) -> None:
        from hypokrates.dailymed.models import LabelCheckResult
        from hypokrates.mcp.tools import dailymed

        capture = ToolCapture()
        dailymed.register(capture)  # type: ignore[arg-type]

        mock_result = LabelCheckResult(
            drug="propofol",
            event="bradycardia",
            in_label=True,
            matched_terms=["bradycardia"],
            set_id="abc-123",
            meta=_make_meta("DailyMed"),
        )

        with patch.object(dailymed, "dailymed_api") as mock_api:
            mock_api.check_label = AsyncMock(return_value=mock_result)
            result = await capture.tools["check_label"]("propofol", "bradycardia")

        assert "YES" in result
        assert "bradycardia" in result
        assert "abc-123" in result

    async def test_check_label_not_found(self) -> None:
        from hypokrates.dailymed.models import LabelCheckResult
        from hypokrates.mcp.tools import dailymed

        capture = ToolCapture()
        dailymed.register(capture)  # type: ignore[arg-type]

        mock_result = LabelCheckResult(
            drug="propofol",
            event="anhedonia",
            in_label=False,
            meta=_make_meta("DailyMed"),
        )

        with patch.object(dailymed, "dailymed_api") as mock_api:
            mock_api.check_label = AsyncMock(return_value=mock_result)
            result = await capture.tools["check_label"]("propofol", "anhedonia")

        assert "NO" in result


# ---------------------------------------------------------------------------
# Tests: Trials tools
# ---------------------------------------------------------------------------


class TestTrialsTools:
    """MCP tools para ClinicalTrials.gov."""

    async def test_search_trials_found(self) -> None:
        from hypokrates.mcp.tools import trials
        from hypokrates.trials.models import ClinicalTrial, TrialsResult

        capture = ToolCapture()
        trials.register(capture)  # type: ignore[arg-type]

        mock_result = TrialsResult(
            drug="propofol",
            event="hypotension",
            total_count=2,
            active_count=1,
            trials=[
                ClinicalTrial(
                    nct_id="NCT12345678",
                    title="Propofol hypotension study",
                    status="RECRUITING",
                    phase="Phase 3",
                ),
            ],
            meta=_make_meta("ClinicalTrials.gov"),
        )

        with patch.object(trials, "trials_api") as mock_api:
            mock_api.search_trials = AsyncMock(return_value=mock_result)
            result = await capture.tools["search_trials"]("propofol", "hypotension")

        assert "PROPOFOL" in result
        assert "NCT12345678" in result
        assert "RECRUITING" in result
        assert "Phase 3" in result

    async def test_search_trials_empty(self) -> None:
        from hypokrates.mcp.tools import trials
        from hypokrates.trials.models import TrialsResult

        capture = ToolCapture()
        trials.register(capture)  # type: ignore[arg-type]

        mock_result = TrialsResult(
            drug="xyz",
            event="abc",
            total_count=0,
            active_count=0,
            trials=[],
            meta=_make_meta("ClinicalTrials.gov"),
        )

        with patch.object(trials, "trials_api") as mock_api:
            mock_api.search_trials = AsyncMock(return_value=mock_result)
            result = await capture.tools["search_trials"]("xyz", "abc")

        assert "No matching trials found" in result


# ---------------------------------------------------------------------------
# Tests: DrugBank tools
# ---------------------------------------------------------------------------


class TestDrugBankTools:
    """MCP tools para DrugBank."""

    async def test_drug_info_found(self) -> None:
        from hypokrates.drugbank.models import (
            DrugBankInfo,
            DrugEnzyme,
            DrugInteraction,
            DrugTarget,
        )
        from hypokrates.mcp.tools import drugbank

        capture = ToolCapture()
        drugbank.register(capture)  # type: ignore[arg-type]

        mock_result = DrugBankInfo(
            drugbank_id="DB00818",
            name="Propofol",
            mechanism_of_action="GABA-A receptor potentiator for general anesthesia.",
            targets=[
                DrugTarget(name="GABA-A receptor", gene_name="GABRA1", actions=["potentiator"]),
            ],
            enzymes=[DrugEnzyme(name="CYP2B6", gene_name="CYP2B6")],
            interactions=[
                DrugInteraction(
                    partner_id="DB00813",
                    partner_name="Fentanyl",
                    description="May enhance CNS depression",
                ),
            ],
        )

        with patch.object(drugbank, "drugbank_api") as mock_api:
            mock_api.drug_info = AsyncMock(return_value=mock_result)
            result = await capture.tools["drug_info"]("propofol")

        assert "Propofol" in result
        assert "DB00818" in result
        assert "GABA-A" in result
        assert "GABRA1" in result
        assert "CYP2B6" in result
        assert "Fentanyl" in result

    async def test_drug_info_not_found(self) -> None:
        from hypokrates.mcp.tools import drugbank

        capture = ToolCapture()
        drugbank.register(capture)  # type: ignore[arg-type]

        with patch.object(drugbank, "drugbank_api") as mock_api:
            mock_api.drug_info = AsyncMock(return_value=None)
            result = await capture.tools["drug_info"]("unknowndrug")

        assert "not found" in result

    async def test_drug_interactions_found(self) -> None:
        from hypokrates.drugbank.models import DrugInteraction
        from hypokrates.mcp.tools import drugbank

        capture = ToolCapture()
        drugbank.register(capture)  # type: ignore[arg-type]

        mock_result = [
            DrugInteraction(
                partner_id="DB00813",
                partner_name="Fentanyl",
                description="May enhance CNS depression",
            ),
            DrugInteraction(
                partner_id="DB00921",
                partner_name="Midazolam",
                description="Additive sedation",
            ),
        ]

        with patch.object(drugbank, "drugbank_api") as mock_api:
            mock_api.drug_interactions = AsyncMock(return_value=mock_result)
            result = await capture.tools["drug_interactions"]("propofol")

        assert "PROPOFOL" in result
        assert "Fentanyl" in result
        assert "Midazolam" in result
        assert "2" in result  # total count

    async def test_drug_interactions_empty(self) -> None:
        from hypokrates.mcp.tools import drugbank

        capture = ToolCapture()
        drugbank.register(capture)  # type: ignore[arg-type]

        with patch.object(drugbank, "drugbank_api") as mock_api:
            mock_api.drug_interactions = AsyncMock(return_value=[])
            result = await capture.tools["drug_interactions"]("unknowndrug")

        assert "No interactions found" in result


# ---------------------------------------------------------------------------
# Tests: OpenTargets tools
# ---------------------------------------------------------------------------


class TestOpenTargetsTools:
    """MCP tools para OpenTargets."""

    async def test_drug_adverse_events_found(self) -> None:
        from hypokrates.mcp.tools import opentargets
        from hypokrates.opentargets.models import OTAdverseEvent, OTDrugSafety

        capture = ToolCapture()
        opentargets.register(capture)  # type: ignore[arg-type]

        mock_result = OTDrugSafety(
            drug_name="propofol",
            chembl_id="CHEMBL526",
            adverse_events=[
                OTAdverseEvent(name="Bradycardia", count=150, log_lr=5.2, meddra_code="10006093"),
                OTAdverseEvent(name="Hypotension", count=300, log_lr=4.8),
            ],
            total_count=2,
            critical_value=9.49,
            meta=_make_meta("OpenTargets"),
        )

        with patch.object(opentargets, "opentargets_api") as mock_api:
            mock_api.drug_adverse_events = AsyncMock(return_value=mock_result)
            result = await capture.tools["drug_adverse_events"]("propofol")

        assert "PROPOFOL" in result
        assert "CHEMBL526" in result
        assert "Bradycardia" in result
        assert "10006093" in result
        assert "Hypotension" in result

    async def test_drug_adverse_events_not_found(self) -> None:
        from hypokrates.mcp.tools import opentargets
        from hypokrates.opentargets.models import OTDrugSafety

        capture = ToolCapture()
        opentargets.register(capture)  # type: ignore[arg-type]

        mock_result = OTDrugSafety(
            drug_name="unknowndrug",
            chembl_id="",
            meta=_make_meta("OpenTargets"),
        )

        with patch.object(opentargets, "opentargets_api") as mock_api:
            mock_api.drug_adverse_events = AsyncMock(return_value=mock_result)
            result = await capture.tools["drug_adverse_events"]("unknowndrug")

        assert "not found" in result

    async def test_drug_safety_score_found(self) -> None:
        from hypokrates.mcp.tools import opentargets

        capture = ToolCapture()
        opentargets.register(capture)  # type: ignore[arg-type]

        with patch.object(opentargets, "opentargets_api") as mock_api:
            mock_api.drug_safety_score = AsyncMock(return_value=5.2345)
            result = await capture.tools["drug_safety_score"]("propofol", "bradycardia")

        assert "PROPOFOL" in result
        assert "BRADYCARDIA" in result
        assert "5.2345" in result

    async def test_drug_safety_score_not_found(self) -> None:
        from hypokrates.mcp.tools import opentargets

        capture = ToolCapture()
        opentargets.register(capture)  # type: ignore[arg-type]

        with patch.object(opentargets, "opentargets_api") as mock_api:
            mock_api.drug_safety_score = AsyncMock(return_value=None)
            result = await capture.tools["drug_safety_score"]("xyz", "abc")

        assert "No OpenTargets LRT score found" in result


# ---------------------------------------------------------------------------
# Tests: ChEMBL tools
# ---------------------------------------------------------------------------


class TestChEMBLTools:
    """MCP tools para ChEMBL."""

    async def test_drug_mechanism_found(self) -> None:
        from hypokrates.chembl.models import ChEMBLMechanism, ChEMBLTarget
        from hypokrates.mcp.tools import chembl

        capture = ToolCapture()
        chembl.register(capture)  # type: ignore[arg-type]

        mock_result = ChEMBLMechanism(
            chembl_id="CHEMBL526",
            drug_name="Propofol",
            mechanism_of_action="GABA-A receptor positive allosteric modulator",
            action_type="POSITIVE ALLOSTERIC MODULATOR",
            max_phase=4,
            targets=[
                ChEMBLTarget(
                    target_chembl_id="CHEMBL2093872",
                    name="GABA-A receptor",
                    gene_names=["GABRA1", "GABRA2"],
                    organism="Homo sapiens",
                ),
            ],
            meta=_make_meta("ChEMBL"),
        )

        with patch.object(chembl, "chembl_api") as mock_api:
            mock_api.drug_mechanism = AsyncMock(return_value=mock_result)
            result = await capture.tools["drug_mechanism"]("propofol")

        assert "Propofol" in result
        assert "CHEMBL526" in result
        assert "GABA-A" in result
        assert "GABRA1" in result
        assert "Max phase:** 4" in result

    async def test_drug_mechanism_not_found(self) -> None:
        from hypokrates.chembl.models import ChEMBLMechanism
        from hypokrates.mcp.tools import chembl

        capture = ToolCapture()
        chembl.register(capture)  # type: ignore[arg-type]

        mock_result = ChEMBLMechanism(
            chembl_id="",
            meta=_make_meta("ChEMBL"),
        )

        with patch.object(chembl, "chembl_api") as mock_api:
            mock_api.drug_mechanism = AsyncMock(return_value=mock_result)
            result = await capture.tools["drug_mechanism"]("xyz123")

        assert "not found in ChEMBL" in result

    async def test_drug_metabolism_found(self) -> None:
        from hypokrates.chembl.models import ChEMBLMetabolism, MetabolismPathway
        from hypokrates.mcp.tools import chembl

        capture = ToolCapture()
        chembl.register(capture)  # type: ignore[arg-type]

        mock_result = ChEMBLMetabolism(
            chembl_id="CHEMBL526",
            drug_name="Propofol",
            pathways=[
                MetabolismPathway(
                    enzyme_name="CYP2B6",
                    substrate_name="Propofol",
                    metabolite_name="4-Hydroxypropofol",
                    conversion="Hydroxylation",
                ),
            ],
            meta=_make_meta("ChEMBL"),
        )

        with patch.object(chembl, "chembl_api") as mock_api:
            mock_api.drug_metabolism = AsyncMock(return_value=mock_result)
            result = await capture.tools["drug_metabolism"]("propofol")

        assert "Propofol" in result
        assert "CYP2B6" in result
        assert "4-Hydroxypropofol" in result
        assert "Hydroxylation" in result

    async def test_drug_metabolism_not_found(self) -> None:
        from hypokrates.chembl.models import ChEMBLMetabolism
        from hypokrates.mcp.tools import chembl

        capture = ToolCapture()
        chembl.register(capture)  # type: ignore[arg-type]

        mock_result = ChEMBLMetabolism(
            chembl_id="",
            meta=_make_meta("ChEMBL"),
        )

        with patch.object(chembl, "chembl_api") as mock_api:
            mock_api.drug_metabolism = AsyncMock(return_value=mock_result)
            result = await capture.tools["drug_metabolism"]("xyz123")

        assert "not found in ChEMBL" in result

    async def test_drug_metabolism_no_pathways(self) -> None:
        from hypokrates.chembl.models import ChEMBLMetabolism
        from hypokrates.mcp.tools import chembl

        capture = ToolCapture()
        chembl.register(capture)  # type: ignore[arg-type]

        mock_result = ChEMBLMetabolism(
            chembl_id="CHEMBL526",
            drug_name="Propofol",
            pathways=[],
            meta=_make_meta("ChEMBL"),
        )

        with patch.object(chembl, "chembl_api") as mock_api:
            mock_api.drug_metabolism = AsyncMock(return_value=mock_result)
            result = await capture.tools["drug_metabolism"]("propofol")

        assert "No metabolism data available" in result


# ---------------------------------------------------------------------------
# Tests: FAERS Bulk tools
# ---------------------------------------------------------------------------


class TestFAERSBulkTools:
    """MCP tools para FAERS Bulk."""

    async def test_bulk_status_loaded(self) -> None:
        from hypokrates.faers_bulk.models import BulkStoreStatus, QuarterInfo
        from hypokrates.mcp.tools import faers_bulk

        capture = ToolCapture()
        faers_bulk.register(capture)  # type: ignore[arg-type]

        mock_status = BulkStoreStatus(
            total_reports=50000,
            deduped_cases=45000,
            quarters_loaded=[
                QuarterInfo(
                    quarter_key="2024Q3",
                    year=2024,
                    quarter=3,
                    loaded_at=datetime.now(UTC),
                    demo_count=25000,
                    drug_count=80000,
                    reac_count=60000,
                ),
            ],
            oldest_quarter="2024Q3",
            newest_quarter="2024Q3",
        )

        with patch.object(faers_bulk, "bulk_api") as mock_api:
            mock_api.bulk_store_status = AsyncMock(return_value=mock_status)
            result = await capture.tools["faers_bulk_status"]()

        assert "50,000" in result
        assert "45,000" in result
        assert "2024Q3" in result

    async def test_bulk_status_empty(self) -> None:
        from hypokrates.faers_bulk.models import BulkStoreStatus
        from hypokrates.mcp.tools import faers_bulk

        capture = ToolCapture()
        faers_bulk.register(capture)  # type: ignore[arg-type]

        mock_status = BulkStoreStatus(
            total_reports=0,
            deduped_cases=0,
            quarters_loaded=[],
        )

        with patch.object(faers_bulk, "bulk_api") as mock_api:
            mock_api.bulk_store_status = AsyncMock(return_value=mock_status)
            result = await capture.tools["faers_bulk_status"]()

        assert "Empty" in result
        assert "faers_bulk_load" in result

    async def test_bulk_status_error(self) -> None:
        from hypokrates.mcp.tools import faers_bulk

        capture = ToolCapture()
        faers_bulk.register(capture)  # type: ignore[arg-type]

        with patch.object(faers_bulk, "bulk_api") as mock_api:
            mock_api.bulk_store_status = AsyncMock(side_effect=RuntimeError("No store"))
            result = await capture.tools["faers_bulk_status"]()

        assert "not available" in result

    async def test_bulk_signal_detected(self) -> None:
        from hypokrates.mcp.tools import faers_bulk

        capture = ToolCapture()
        faers_bulk.register(capture)  # type: ignore[arg-type]

        mock_signal = _make_signal("propofol", "BRADYCARDIA")

        with patch.object(faers_bulk, "bulk_api") as mock_api:
            mock_api.is_bulk_available = AsyncMock(return_value=True)
            mock_api.bulk_signal = AsyncMock(return_value=mock_signal)
            result = await capture.tools["faers_bulk_signal"]("propofol", "BRADYCARDIA", "suspect")

        assert "PROPOFOL" in result
        assert "BRADYCARDIA" in result
        assert "Signal detected:** YES" in result

    async def test_bulk_signal_store_empty(self) -> None:
        from hypokrates.mcp.tools import faers_bulk

        capture = ToolCapture()
        faers_bulk.register(capture)  # type: ignore[arg-type]

        with patch.object(faers_bulk, "bulk_api") as mock_api:
            mock_api.is_bulk_available = AsyncMock(return_value=False)
            result = await capture.tools["faers_bulk_signal"]("propofol", "DEATH", "suspect")

        assert "empty" in result.lower()

    async def test_bulk_signal_invalid_role(self) -> None:
        from hypokrates.mcp.tools import faers_bulk

        capture = ToolCapture()
        faers_bulk.register(capture)  # type: ignore[arg-type]

        with patch.object(faers_bulk, "bulk_api") as mock_api:
            mock_api.is_bulk_available = AsyncMock(return_value=True)
            result = await capture.tools["faers_bulk_signal"]("propofol", "DEATH", "invalid_role")

        assert "Invalid role_filter" in result

    async def test_bulk_load_success(self) -> None:
        from hypokrates.faers_bulk.models import BulkStoreStatus
        from hypokrates.mcp.tools import faers_bulk

        capture = ToolCapture()
        faers_bulk.register(capture)  # type: ignore[arg-type]

        mock_status = BulkStoreStatus(
            total_reports=50000,
            deduped_cases=45000,
            quarters_loaded=[],
        )

        with (
            patch(
                "hypokrates.faers_bulk.loader.load_incremental", new_callable=AsyncMock
            ) as mock_load,
            patch.object(faers_bulk, "bulk_api") as mock_api,
        ):
            mock_load.return_value = 25000
            mock_api.bulk_store_status = AsyncMock(return_value=mock_status)
            result = await capture.tools["faers_bulk_load"]("/path/to/zips")

        assert "25,000" in result

    async def test_bulk_load_nothing_new(self) -> None:
        from hypokrates.mcp.tools import faers_bulk

        capture = ToolCapture()
        faers_bulk.register(capture)  # type: ignore[arg-type]

        with patch(
            "hypokrates.faers_bulk.loader.load_incremental", new_callable=AsyncMock
        ) as mock_load:
            mock_load.return_value = 0
            result = await capture.tools["faers_bulk_load"]("/path/to/zips")

        assert "No new quarters" in result

    async def test_bulk_load_error(self) -> None:
        from hypokrates.mcp.tools import faers_bulk

        capture = ToolCapture()
        faers_bulk.register(capture)  # type: ignore[arg-type]

        with patch(
            "hypokrates.faers_bulk.loader.load_incremental", new_callable=AsyncMock
        ) as mock_load:
            mock_load.side_effect = RuntimeError("Disk full")
            result = await capture.tools["faers_bulk_load"]("/path/to/zips")

        assert "Error loading" in result

    async def test_bulk_timeline(self) -> None:
        from hypokrates.mcp.tools import faers_bulk
        from hypokrates.stats.models import QuarterlyCount, TimelineResult

        capture = ToolCapture()
        faers_bulk.register(capture)  # type: ignore[arg-type]

        mock_result = TimelineResult(
            drug="propofol",
            event="BRADYCARDIA",
            quarters=[
                QuarterlyCount(year=2023, quarter=1, count=10, label="2023-Q1"),
                QuarterlyCount(year=2023, quarter=2, count=50, label="2023-Q2"),
                QuarterlyCount(year=2023, quarter=3, count=8, label="2023-Q3"),
            ],
            total_reports=68,
            peak_quarter=QuarterlyCount(year=2023, quarter=2, count=50, label="2023-Q2"),
            mean_quarterly=22.7,
            std_quarterly=23.5,
            spike_quarters=[
                QuarterlyCount(year=2023, quarter=2, count=50, label="2023-Q2"),
            ],
            suspect_only=False,
            meta=_make_meta("FAERS/bulk"),
        )

        with (
            patch.object(faers_bulk, "bulk_api") as mock_api,
            patch(
                "hypokrates.mcp.tools.faers_bulk.bulk_signal_timeline", new_callable=AsyncMock
            ) as mock_timeline,
        ):
            mock_api.is_bulk_available = AsyncMock(return_value=True)
            mock_timeline.return_value = mock_result
            result = await capture.tools["faers_bulk_timeline"]("propofol", "BRADYCARDIA")

        assert "PROPOFOL" in result
        assert "BRADYCARDIA" in result
        assert "2023-Q2" in result
        assert "SPIKE" in result

    async def test_bulk_timeline_store_empty(self) -> None:
        from hypokrates.mcp.tools import faers_bulk

        capture = ToolCapture()
        faers_bulk.register(capture)  # type: ignore[arg-type]

        with patch.object(faers_bulk, "bulk_api") as mock_api:
            mock_api.is_bulk_available = AsyncMock(return_value=False)
            result = await capture.tools["faers_bulk_timeline"]("propofol", "DEATH")

        assert "empty" in result.lower()

    async def test_bulk_timeline_invalid_role(self) -> None:
        from hypokrates.mcp.tools import faers_bulk

        capture = ToolCapture()
        faers_bulk.register(capture)  # type: ignore[arg-type]

        with patch.object(faers_bulk, "bulk_api") as mock_api:
            mock_api.is_bulk_available = AsyncMock(return_value=True)
            result = await capture.tools["faers_bulk_timeline"]("propofol", "DEATH", "bad_role")

        assert "Invalid role_filter" in result


# ---------------------------------------------------------------------------
# Tests: Stats tools extended (batch_signal, signal_timeline)
# ---------------------------------------------------------------------------


class TestStatsToolsExtended:
    """MCP tools de stats — batch e timeline."""

    async def test_batch_signal(self) -> None:
        from hypokrates.mcp.tools import stats

        capture = ToolCapture()
        stats.register(capture)  # type: ignore[arg-type]

        pairs = [
            {"drug": "propofol", "event": "BRADYCARDIA"},
            {"drug": "ketamine", "event": "HALLUCINATION"},
        ]

        with patch.object(stats, "stats_api") as mock_api:
            mock_api.signal = AsyncMock(
                side_effect=[
                    _make_signal("propofol", "BRADYCARDIA"),
                    _make_signal("ketamine", "HALLUCINATION"),
                ]
            )
            with patch.object(stats, "FAERSClient") as mock_cls:
                mock_cls.return_value.close = AsyncMock()
                result = await capture.tools["batch_signal"](pairs)

        assert "Batch Signal Detection" in result
        assert "PROPOFOL" in result
        assert "KETAMINE" in result
        assert "2 pairs" in result

    async def test_batch_signal_empty(self) -> None:
        from hypokrates.mcp.tools import stats

        capture = ToolCapture()
        stats.register(capture)  # type: ignore[arg-type]

        result = await capture.tools["batch_signal"]([])
        assert "No pairs provided" in result

    async def test_batch_signal_with_error(self) -> None:
        from hypokrates.mcp.tools import stats

        capture = ToolCapture()
        stats.register(capture)  # type: ignore[arg-type]

        pairs = [
            {"drug": "propofol", "event": "DEATH"},
            {"drug": "bad", "event": "ERROR"},
        ]

        with patch.object(stats, "stats_api") as mock_api:
            mock_api.signal = AsyncMock(
                side_effect=[
                    _make_signal("propofol", "DEATH"),
                    RuntimeError("API failed"),
                ]
            )
            with patch.object(stats, "FAERSClient") as mock_cls:
                mock_cls.return_value.close = AsyncMock()
                result = await capture.tools["batch_signal"](pairs)

        assert "PROPOFOL" in result
        assert "Error" in result

    async def test_signal_timeline(self) -> None:
        from hypokrates.mcp.tools import stats
        from hypokrates.stats.models import QuarterlyCount, TimelineResult

        capture = ToolCapture()
        stats.register(capture)  # type: ignore[arg-type]

        mock_result = TimelineResult(
            drug="propofol",
            event="anhedonia",
            quarters=[
                QuarterlyCount(year=2022, quarter=1, count=5, label="2022-Q1"),
                QuarterlyCount(year=2022, quarter=2, count=3, label="2022-Q2"),
                QuarterlyCount(year=2022, quarter=3, count=30, label="2022-Q3"),
            ],
            total_reports=38,
            peak_quarter=QuarterlyCount(year=2022, quarter=3, count=30, label="2022-Q3"),
            mean_quarterly=12.7,
            std_quarterly=15.1,
            spike_quarters=[
                QuarterlyCount(year=2022, quarter=3, count=30, label="2022-Q3"),
            ],
            suspect_only=False,
            meta=_make_meta("OpenFDA/FAERS"),
        )

        with patch.object(stats, "stats_api") as mock_api:
            mock_api.signal_timeline = AsyncMock(return_value=mock_result)
            result = await capture.tools["signal_timeline"]("propofol", "anhedonia")

        assert "PROPOFOL" in result
        assert "ANHEDONIA" in result
        assert "2022-Q3" in result
        assert "SPIKE" in result
        assert "38" in result

    async def test_signal_timeline_no_spikes(self) -> None:
        from hypokrates.mcp.tools import stats
        from hypokrates.stats.models import QuarterlyCount, TimelineResult

        capture = ToolCapture()
        stats.register(capture)  # type: ignore[arg-type]

        mock_result = TimelineResult(
            drug="propofol",
            event="nausea",
            quarters=[
                QuarterlyCount(year=2023, quarter=1, count=5, label="2023-Q1"),
            ],
            total_reports=5,
            peak_quarter=QuarterlyCount(year=2023, quarter=1, count=5, label="2023-Q1"),
            mean_quarterly=5.0,
            std_quarterly=0.0,
            spike_quarters=[],
            suspect_only=False,
            meta=_make_meta("OpenFDA/FAERS"),
        )

        with patch.object(stats, "stats_api") as mock_api:
            mock_api.signal_timeline = AsyncMock(return_value=mock_result)
            result = await capture.tools["signal_timeline"]("propofol", "nausea")

        assert "Spikes detected:** none" in result


# ---------------------------------------------------------------------------
# Tests: Cross tools extended (hypothesis with enrichment, compare_signals)
# ---------------------------------------------------------------------------


class TestCrossToolsExtended:
    """MCP tools de cross — enriquecimento e compare_signals."""

    async def test_hypothesis_with_label_and_trials(self) -> None:
        from hypokrates.mcp.tools import cross

        capture = ToolCapture()
        cross.register(capture)  # type: ignore[arg-type]

        mock_result = HypothesisResult(
            drug="propofol",
            event="ANHEDONIA",
            classification=HypothesisClassification.NOVEL_HYPOTHESIS,
            signal=_make_signal("propofol", "ANHEDONIA"),
            literature_count=0,
            articles=[],
            evidence=_make_evidence(),
            summary="Novel hypothesis for anhedonia.",
            in_label=False,
            label_detail="Not found in adverse reactions section",
            active_trials=2,
            trials_detail="2 trials found",
            mechanism="GABA-A potentiator",
            enzymes=["CYP2B6"],
            ot_llr=3.14,
        )

        with patch.object(cross, "cross_api") as mock_api:
            mock_api.hypothesis = AsyncMock(return_value=mock_result)
            result = await capture.tools["hypothesis"](
                "propofol",
                "ANHEDONIA",
                check_label=True,
                check_trials=True,
                check_opentargets=True,
            )

        assert "FDA label:** NO" in result
        assert "Active trials:** 2" in result
        assert "GABA-A potentiator" in result
        assert "CYP2B6" in result
        assert "3.14" in result

    async def test_compare_signals(self) -> None:
        from hypokrates.cross.models import CompareResult, CompareSignalItem
        from hypokrates.mcp.tools import cross

        capture = ToolCapture()
        cross.register(capture)  # type: ignore[arg-type]

        mock_result = CompareResult(
            drug="isotretinoin",
            control="doxycycline",
            items=[
                CompareSignalItem(
                    event="DEPRESSION",
                    drug_prr=3.5,
                    control_prr=0.8,
                    drug_detected=True,
                    control_detected=False,
                    ratio=4.375,
                    stronger="drug",
                ),
            ],
            drug_unique_signals=1,
            control_unique_signals=0,
            both_detected=0,
            total_events=1,
            meta=_make_meta("hypokrates/compare"),
        )

        with patch.object(cross, "cross_api") as mock_api:
            mock_api.compare_signals = AsyncMock(return_value=mock_result)
            result = await capture.tools["compare_signals"](
                "isotretinoin", "doxycycline", "DEPRESSION"
            )

        assert "ISOTRETINOIN" in result
        assert "DOXYCYCLINE" in result
        assert "DEPRESSION" in result
        assert "3.50" in result
        assert "4.4x" in result


# ---------------------------------------------------------------------------
# Tests: Scan tools extended (enrichment, compare_class, error)
# ---------------------------------------------------------------------------


class TestScanToolsExtended:
    """MCP tools de scan — enriquecimento e compare_class."""

    async def test_scan_drug_with_enrichment(self) -> None:
        """scan_drug com mechanism, cyp_enzymes, interactions_count."""
        from hypokrates.mcp.tools import scan

        capture = ToolCapture()
        scan.register(capture)  # type: ignore[arg-type]

        mock_result = ScanResult(
            drug="propofol",
            items=[
                ScanItem(
                    drug="propofol",
                    event="BRADYCARDIA",
                    classification=HypothesisClassification.KNOWN_ASSOCIATION,
                    signal=_make_signal("propofol", "BRADYCARDIA"),
                    literature_count=10,
                    evidence=_make_evidence(),
                    summary="Known.",
                    score=4.5,
                    rank=1,
                    in_label=True,
                    active_trials=3,
                    ot_llr=5.2,
                    grouped_terms=["BRADYCARDIA", "SINUS BRADYCARDIA"],
                    volume_flag=True,
                    is_indication=True,
                    cluster="Cardiovascular",
                ),
            ],
            total_scanned=1,
            known_count=1,
            labeled_count=1,
            filtered_operational_count=2,
            groups_applied=True,
            mechanism="GABA-A potentiator",
            interactions_count=5,
            cyp_enzymes=["CYP2B6"],
            meta=_make_meta(),
        )

        with patch.object(scan, "scan_api") as mock_api:
            mock_api.scan_drug = AsyncMock(return_value=mock_result)
            result = await capture.tools["scan_drug"]("propofol", 5)

        assert "label=YES" in result
        assert "trials=3" in result
        assert "logLR=5.20" in result
        assert "grouped:" in result
        assert "VOLUME" in result
        assert "INDICATION" in result
        assert "Cardiovascular" in result
        assert "GABA-A potentiator" in result
        assert "CYP2B6" in result
        assert "5 drug interactions" in result
        assert "2 operational filtered" in result
        assert "MedDRA grouped" in result

    async def test_scan_drug_error(self) -> None:
        """scan_drug retorna erro quando API falha."""
        from hypokrates.mcp.tools import scan

        capture = ToolCapture()
        scan.register(capture)  # type: ignore[arg-type]

        with patch.object(scan, "scan_api") as mock_api:
            mock_api.scan_drug = AsyncMock(side_effect=RuntimeError("FAERS down"))
            result = await capture.tools["scan_drug"]("propofol", 5)

        assert "ERROR" in result
        assert "FAERS down" in result

    async def test_compare_class_success(self) -> None:
        from hypokrates.mcp.tools import scan
        from hypokrates.scan.models import (
            ClassCompareResult,
            ClassEventItem,
            EventClassification,
        )

        capture = ToolCapture()
        scan.register(capture)  # type: ignore[arg-type]

        mock_result = ClassCompareResult(
            drugs=["drug_a", "drug_b"],
            items=[
                ClassEventItem(
                    event="NAUSEA",
                    classification=EventClassification.CLASS_EFFECT,
                    signals={},
                    drugs_with_signal=["drug_a", "drug_b"],
                    drugs_without_signal=[],
                    strongest_drug="drug_a",
                    prr_values={"drug_a": 3.0, "drug_b": 2.5},
                    max_prr=3.0,
                    median_prr=2.75,
                ),
                ClassEventItem(
                    event="RASH",
                    classification=EventClassification.DRUG_SPECIFIC,
                    signals={},
                    drugs_with_signal=["drug_a"],
                    drugs_without_signal=["drug_b"],
                    strongest_drug="drug_a",
                    prr_values={"drug_a": 5.0, "drug_b": 0.5},
                    max_prr=5.0,
                    median_prr=5.0,
                ),
            ],
            class_effect_count=1,
            drug_specific_count=1,
            differential_count=0,
            total_events=2,
            class_threshold_used=0.75,
            outlier_factor_used=3.0,
            meta=_make_meta(),
        )

        with patch.object(scan, "class_compare_api") as mock_api:
            mock_api.compare_class = AsyncMock(return_value=mock_result)
            result = await capture.tools["compare_class"]("drug_a,drug_b", 30)

        assert "DRUG_A" in result
        assert "DRUG_B" in result
        assert "Class Effects" in result
        assert "NAUSEA" in result
        assert "Drug-Specific" in result
        assert "RASH" in result

    async def test_compare_class_too_few_drugs(self) -> None:
        from hypokrates.mcp.tools import scan

        capture = ToolCapture()
        scan.register(capture)  # type: ignore[arg-type]

        result = await capture.tools["compare_class"]("only_one")
        assert "ERROR" in result
        assert "2 drugs" in result

    async def test_compare_class_error(self) -> None:
        from hypokrates.mcp.tools import scan

        capture = ToolCapture()
        scan.register(capture)  # type: ignore[arg-type]

        with patch.object(scan, "class_compare_api") as mock_api:
            mock_api.compare_class = AsyncMock(side_effect=RuntimeError("FAERS down"))
            result = await capture.tools["compare_class"]("drug_a,drug_b")

        assert "ERROR" in result

    async def test_compare_class_differential_with_outlier(self) -> None:
        from hypokrates.mcp.tools import scan
        from hypokrates.scan.models import (
            ClassCompareResult,
            ClassEventItem,
            EventClassification,
        )

        capture = ToolCapture()
        scan.register(capture)  # type: ignore[arg-type]

        mock_result = ClassCompareResult(
            drugs=["drug_a", "drug_b", "drug_c"],
            items=[
                ClassEventItem(
                    event="HEPATOTOXICITY",
                    classification=EventClassification.DIFFERENTIAL,
                    signals={},
                    drugs_with_signal=["drug_a", "drug_b", "drug_c"],
                    drugs_without_signal=[],
                    strongest_drug="drug_a",
                    prr_values={"drug_a": 30.0, "drug_b": 2.0, "drug_c": 2.5},
                    max_prr=30.0,
                    median_prr=2.5,
                    outlier_drug="drug_a",
                    outlier_factor=12.0,
                ),
            ],
            class_effect_count=0,
            drug_specific_count=0,
            differential_count=1,
            total_events=1,
            class_threshold_used=0.75,
            outlier_factor_used=3.0,
            meta=_make_meta(),
        )

        with patch.object(scan, "class_compare_api") as mock_api:
            mock_api.compare_class = AsyncMock(return_value=mock_result)
            result = await capture.tools["compare_class"]("drug_a,drug_b,drug_c")

        assert "Differential" in result
        assert "HEPATOTOXICITY" in result
        assert "DRUG_A" in result
        assert "12.0x median" in result


# ---------------------------------------------------------------------------
# Tests: MCP server — create_server
# ---------------------------------------------------------------------------


class TestMCPServer:
    """Teste do create_server."""

    def test_create_server_registers_all_tools(self) -> None:
        """create_server registra tools sem erro."""
        from hypokrates.mcp.server import create_server

        server = create_server()
        assert server is not None
