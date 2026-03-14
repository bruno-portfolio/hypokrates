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

        assert "12 tools" in result
        assert "adverse_events" in result
        assert "scan_drug" in result
        assert "normalize_drug" in result
        assert "version" in result

    async def test_version(self) -> None:
        from hypokrates.mcp.tools import meta

        capture = ToolCapture()
        meta.register(capture)  # type: ignore[arg-type]

        result = await capture.tools["version"]()

        assert __version__ in result
        assert "Sprint" in result
        assert "12" in result
