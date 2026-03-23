"""Testes para hypokrates.cross.report — mock investigate + scan + compare."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest

from hypokrates.cross.models import (
    CompareResult,
    CompareSignalItem,
    HypothesisClassification,
    HypothesisResult,
    InvestigationResult,
    StratumSignal,
    SynthesisDirection,
)
from hypokrates.cross.report import (
    FullReportResult,
    _build_synthesis,
    _compute_class_effect,
    _compute_signal_strength,
    full_report_analysis,
)
from hypokrates.scan.models import ScanItem, ScanResult
from tests.helpers import make_evidence, make_meta, make_signal

# ---------------------------------------------------------------------------
# Factories
# ---------------------------------------------------------------------------


def _make_hypothesis(
    *,
    prr: float = 3.0,
    detected: bool = True,
    a: int = 100,
    lit: int = 15,
    classification: HypothesisClassification = HypothesisClassification.KNOWN_ASSOCIATION,
    in_label: bool | None = None,
    mechanism: str | None = None,
    indication_confounding: bool = False,
) -> HypothesisResult:
    return HypothesisResult(
        drug="semaglutide",
        event="BRONCHOSPASM",
        classification=classification,
        signal=make_signal(
            drug="semaglutide", event="BRONCHOSPASM", a=a, prr=prr, detected=detected
        ),
        literature_count=lit,
        evidence=make_evidence(confidence="high", methodology="test"),
        summary="Test summary.",
        in_label=in_label,
        mechanism=mechanism,
        indication_confounding=indication_confounding,
    )


def _make_investigation(
    *,
    prr: float = 3.0,
    detected: bool = True,
    a: int = 100,
    lit: int = 15,
    classification: HypothesisClassification = HypothesisClassification.KNOWN_ASSOCIATION,
    caveats: list[str] | None = None,
    country_strata: list[StratumSignal] | None = None,
    in_label: bool | None = None,
    mechanism: str | None = None,
    indication_confounding: bool = False,
) -> InvestigationResult:
    hyp = _make_hypothesis(
        prr=prr,
        detected=detected,
        a=a,
        lit=lit,
        classification=classification,
        in_label=in_label,
        mechanism=mechanism,
        indication_confounding=indication_confounding,
    )
    return InvestigationResult(
        hypothesis=hyp,
        country_strata=country_strata
        or [
            StratumSignal(
                source="FAERS",
                stratum_type="country",
                stratum_value="FAERS",
                drug_event_count=100,
                prr=prr,
                signal_detected=detected,
            ),
        ],
        caveats=caveats or [],
        meta=make_meta(source="hypokrates/investigate", total=a),
    )


def _make_scan(*, event: str = "BRONCHOSPASM") -> ScanResult:
    return ScanResult(
        drug="semaglutide",
        items=[
            ScanItem(
                drug="semaglutide",
                event="NAUSEA",
                classification=HypothesisClassification.KNOWN_ASSOCIATION,
                signal=make_signal(event="NAUSEA", prr=5.0),
                literature_count=50,
                evidence=make_evidence(),
                summary="Known.",
                score=12.5,
                rank=1,
            ),
            ScanItem(
                drug="semaglutide",
                event="VOMITING",
                classification=HypothesisClassification.EMERGING_SIGNAL,
                signal=make_signal(event="VOMITING", prr=3.0),
                literature_count=5,
                evidence=make_evidence(),
                summary="Emerging.",
                score=8.0,
                rank=2,
            ),
            ScanItem(
                drug="semaglutide",
                event=event.upper(),
                classification=HypothesisClassification.NOVEL_HYPOTHESIS,
                signal=make_signal(event=event.upper(), prr=2.5),
                literature_count=0,
                evidence=make_evidence(),
                summary="Novel.",
                score=6.0,
                rank=3,
            ),
        ],
        total_scanned=20,
        novel_count=1,
        emerging_count=1,
        known_count=1,
        meta=make_meta(source="hypokrates/scan"),
    )


def _make_compare(*, event: str = "BRONCHOSPASM") -> CompareResult:
    return CompareResult(
        drug="semaglutide",
        control="liraglutide",
        items=[
            CompareSignalItem(
                event=event.upper(),
                drug_prr=3.0,
                control_prr=2.5,
                drug_detected=True,
                control_detected=True,
                ratio=1.2,
                stronger="drug",
            ),
            CompareSignalItem(
                event="NAUSEA",
                drug_prr=5.0,
                control_prr=4.5,
                drug_detected=True,
                control_detected=True,
                ratio=1.11,
                stronger="equal",
            ),
        ],
        drug_unique_signals=0,
        control_unique_signals=0,
        both_detected=2,
        total_events=2,
        meta=make_meta(source="hypokrates/compare"),
    )


# ---------------------------------------------------------------------------
# Tests: full_report_analysis orchestration
# ---------------------------------------------------------------------------


class TestFullReport:
    @patch("hypokrates.cross.report.scan_drug", new_callable=AsyncMock)
    @patch("hypokrates.cross.report.investigate", new_callable=AsyncMock)
    async def test_basic_no_control(
        self,
        mock_inv: AsyncMock,
        mock_scan: AsyncMock,
    ) -> None:
        mock_inv.return_value = _make_investigation()
        mock_scan.return_value = _make_scan()

        result = await full_report_analysis("semaglutide", "BRONCHOSPASM")

        assert isinstance(result, FullReportResult)
        assert result.drug == "semaglutide"
        assert result.event == "BRONCHOSPASM"
        assert result.scan is not None
        assert result.comparison is None
        assert result.synthesis.class_effect == "NOT_TESTED"

    @patch("hypokrates.cross.report.compare_signals", new_callable=AsyncMock)
    @patch("hypokrates.cross.report.scan_drug", new_callable=AsyncMock)
    @patch("hypokrates.cross.report.investigate", new_callable=AsyncMock)
    async def test_with_control(
        self,
        mock_inv: AsyncMock,
        mock_scan: AsyncMock,
        mock_compare: AsyncMock,
    ) -> None:
        mock_inv.return_value = _make_investigation()
        mock_scan.return_value = _make_scan()
        mock_compare.return_value = _make_compare()

        result = await full_report_analysis("semaglutide", "BRONCHOSPASM", control="liraglutide")

        assert result.comparison is not None
        assert result.synthesis.class_effect.startswith("YES")
        mock_compare.assert_called_once()

    @patch("hypokrates.cross.report.scan_drug", new_callable=AsyncMock)
    @patch("hypokrates.cross.report.investigate", new_callable=AsyncMock)
    async def test_scan_failure(
        self,
        mock_inv: AsyncMock,
        mock_scan: AsyncMock,
    ) -> None:
        mock_inv.return_value = _make_investigation()
        mock_scan.side_effect = RuntimeError("scan failed")

        result = await full_report_analysis("semaglutide", "BRONCHOSPASM")

        assert result.scan is None
        assert result.synthesis.top_events_context == "unavailable"

    @patch("hypokrates.cross.report.compare_signals", new_callable=AsyncMock)
    @patch("hypokrates.cross.report.scan_drug", new_callable=AsyncMock)
    @patch("hypokrates.cross.report.investigate", new_callable=AsyncMock)
    async def test_compare_failure(
        self,
        mock_inv: AsyncMock,
        mock_scan: AsyncMock,
        mock_compare: AsyncMock,
    ) -> None:
        mock_inv.return_value = _make_investigation()
        mock_scan.return_value = _make_scan()
        mock_compare.side_effect = RuntimeError("compare failed")

        result = await full_report_analysis("semaglutide", "BRONCHOSPASM", control="liraglutide")

        assert result.comparison is None
        assert result.synthesis.class_effect == "NOT_TESTED"

    @patch("hypokrates.cross.report.scan_drug", new_callable=AsyncMock)
    @patch("hypokrates.cross.report.investigate", new_callable=AsyncMock)
    async def test_investigate_failure_raises(
        self,
        mock_inv: AsyncMock,
        mock_scan: AsyncMock,
    ) -> None:
        mock_inv.side_effect = RuntimeError("investigate failed")
        mock_scan.return_value = _make_scan()

        with pytest.raises(RuntimeError, match="investigate failed"):
            await full_report_analysis("semaglutide", "BRONCHOSPASM")


# ---------------------------------------------------------------------------
# Tests: signal_strength computation
# ---------------------------------------------------------------------------


class TestSignalStrength:
    def test_strong(self) -> None:
        inv = _make_investigation(prr=15.0, detected=True)
        result = _compute_signal_strength(inv)
        assert result == "STRONG"

    def test_moderate(self) -> None:
        inv = _make_investigation(prr=3.0, detected=True)
        result = _compute_signal_strength(inv)
        assert result == "MODERATE"

    def test_weak(self) -> None:
        inv = _make_investigation(prr=1.5, detected=True)
        result = _compute_signal_strength(inv)
        assert result == "WEAK"

    def test_none(self) -> None:
        inv = _make_investigation(detected=False)
        result = _compute_signal_strength(inv)
        assert result == "NONE"


# ---------------------------------------------------------------------------
# Tests: class_effect computation
# ---------------------------------------------------------------------------


class TestClassEffect:
    def test_yes_similar_ratio(self) -> None:
        comp = _make_compare()
        result = _compute_class_effect("BRONCHOSPASM", comp, "liraglutide")
        assert result.startswith("YES")
        assert "ratio=1.20" in result

    def test_no_divergent_ratio(self) -> None:
        comp = CompareResult(
            drug="semaglutide",
            control="liraglutide",
            items=[
                CompareSignalItem(
                    event="BRONCHOSPASM",
                    drug_prr=10.0,
                    control_prr=1.0,
                    drug_detected=True,
                    control_detected=False,
                    ratio=10.0,
                    stronger="drug",
                ),
            ],
            total_events=1,
            meta=make_meta(),
        )
        result = _compute_class_effect("BRONCHOSPASM", comp, "liraglutide")
        assert result.startswith("NO")

    def test_not_tested_no_control(self) -> None:
        result = _compute_class_effect("BRONCHOSPASM", None, "")
        assert result == "NOT_TESTED"

    def test_not_in_top_compared(self) -> None:
        comp = _make_compare(event="NAUSEA")
        result = _compute_class_effect("BRONCHOSPASM", comp, "liraglutide")
        assert result == "NOT_IN_TOP_COMPARED"


# ---------------------------------------------------------------------------
# Tests: _build_synthesis integration
# ---------------------------------------------------------------------------


class TestBuildSynthesis:
    def test_full_synthesis(self) -> None:
        inv = _make_investigation(
            prr=3.0,
            detected=True,
            in_label=True,
            mechanism="GLP-1 receptor agonist",
            caveats=["LOW COUNT: Only 5 reports"],
        )
        scan = _make_scan()
        comp = _make_compare()

        syn = _build_synthesis(inv, scan, comp, "liraglutide", "BRONCHOSPASM")

        assert isinstance(syn, SynthesisDirection)
        assert syn.signal_strength == "MODERATE"
        assert syn.classification == "known_association"
        assert syn.reports == 100
        assert syn.caveats_triggered == 1
        assert syn.label_status.startswith("IN_LABEL")
        assert syn.mechanism_plausibility.startswith("KNOWN")
        assert "ranks #3" in syn.top_events_context
        assert syn.class_effect.startswith("YES")
