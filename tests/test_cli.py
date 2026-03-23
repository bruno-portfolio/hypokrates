"""Testes para hypokrates.cli."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING
from unittest.mock import MagicMock, patch

import pytest

from hypokrates.cross.models import CompareResult, CompareSignalItem
from hypokrates.scan.models import ScanItem, ScanResult
from hypokrates.stats.models import (
    QuarterlyCount,
    TimelineResult,
)
from tests.helpers import make_meta, make_signal

try:
    from typer.testing import CliRunner

    from hypokrates.cli import app

    _HAS_TYPER = True
except ImportError:
    _HAS_TYPER = False

if TYPE_CHECKING:
    from typer.testing import CliRunner as CliRunnerType

pytestmark = pytest.mark.skipif(not _HAS_TYPER, reason="typer not installed")

runner: CliRunnerType = CliRunner() if _HAS_TYPER else None  # type: ignore[assignment]


def _make_scan_result(drug: str = "propofol") -> ScanResult:
    from hypokrates.cross.models import HypothesisClassification
    from hypokrates.evidence.models import EvidenceBlock

    sig = make_signal(drug=drug, event="BRADYCARDIA", prr=5.0)
    item = ScanItem(
        drug=drug,
        event="BRADYCARDIA",
        classification=HypothesisClassification.KNOWN_ASSOCIATION,
        signal=sig,
        literature_count=50,
        evidence=EvidenceBlock(source="test", retrieved_at=datetime.now(UTC)),
        summary="test",
        score=10.0,
        rank=1,
        in_label=True,
    )
    return ScanResult(
        drug=drug,
        items=[item],
        total_scanned=1,
        known_count=1,
        meta=make_meta(),
    )


class TestVersionAndHelp:
    def test_version(self) -> None:
        result = runner.invoke(app, ["--version"])
        assert result.exit_code == 0
        assert "hypokrates" in result.output

    def test_no_args_shows_help(self) -> None:
        result = runner.invoke(app, [])
        # Typer com no_args_is_help retorna exit code 0 ou 2 dependendo da versão
        assert result.exit_code in (0, 2)


class TestScanCommand:
    @patch("hypokrates.sync.scan")
    def test_scan_single_drug(self, mock_scan_mod: MagicMock) -> None:
        mock_scan_mod.scan_drug.return_value = _make_scan_result()
        result = runner.invoke(app, ["scan", "propofol"])
        assert result.exit_code == 0
        assert "PROPOFOL" in result.output

    @patch("hypokrates.sync.scan")
    def test_scan_json_output(self, mock_scan_mod: MagicMock) -> None:
        mock_scan_mod.scan_drug.return_value = _make_scan_result()
        result = runner.invoke(app, ["scan", "propofol", "--format", "json"])
        assert result.exit_code == 0
        assert '"drug"' in result.output

    @patch("hypokrates.sync.scan")
    def test_scan_multiple_drugs(self, mock_scan_mod: MagicMock) -> None:
        mock_scan_mod.scan_drug.return_value = _make_scan_result()
        result = runner.invoke(app, ["scan", "propofol", "ketamine"])
        assert result.exit_code == 0
        assert mock_scan_mod.scan_drug.call_count == 2


class TestSignalCommand:
    @patch("hypokrates.sync.stats")
    def test_signal_basic(self, mock_stats: MagicMock) -> None:
        mock_stats.signal.return_value = make_signal(event="BRADYCARDIA", prr=5.0)
        result = runner.invoke(app, ["signal", "propofol", "bradycardia"])
        assert result.exit_code == 0
        assert "PROPOFOL" in result.output
        assert "PRR" in result.output

    @patch("hypokrates.sync.stats")
    def test_signal_json(self, mock_stats: MagicMock) -> None:
        mock_stats.signal.return_value = make_signal(event="BRADYCARDIA", prr=5.0)
        result = runner.invoke(app, ["signal", "propofol", "bradycardia", "-f", "json"])
        assert result.exit_code == 0
        assert '"drug"' in result.output


class TestCompareCommand:
    @patch("hypokrates.sync.cross")
    def test_compare_basic(self, mock_cross: MagicMock) -> None:
        mock_cross.compare_signals.return_value = CompareResult(
            drug="isotretinoin",
            control="doxycycline",
            items=[
                CompareSignalItem(
                    event="DEPRESSION",
                    drug_prr=11.12,
                    control_prr=2.36,
                    drug_detected=True,
                    control_detected=True,
                    ratio=4.7,
                    stronger="drug",
                ),
            ],
            drug_unique_signals=0,
            control_unique_signals=0,
            both_detected=1,
            total_events=1,
            meta=make_meta(),
        )
        result = runner.invoke(app, ["compare", "isotretinoin", "doxycycline"])
        assert result.exit_code == 0
        assert "ISOTRETINOIN" in result.output
        assert "DOXYCYCLINE" in result.output

    @patch("hypokrates.sync.cross")
    def test_compare_with_events(self, mock_cross: MagicMock) -> None:
        mock_cross.compare_signals.return_value = CompareResult(
            drug="a",
            control="b",
            total_events=0,
            meta=make_meta(),
        )
        result = runner.invoke(app, ["compare", "a", "b", "--events", "nausea,headache"])
        assert result.exit_code == 0


class TestTimelineCommand:
    @patch("hypokrates.sync.stats")
    def test_timeline_basic(self, mock_stats: MagicMock) -> None:
        mock_stats.signal_timeline.return_value = TimelineResult(
            drug="etomidate",
            event="anhedonia",
            quarters=[
                QuarterlyCount(year=2023, quarter=1, count=10, label="2023-Q1"),
                QuarterlyCount(year=2023, quarter=2, count=15, label="2023-Q2"),
            ],
            total_reports=25,
            peak_quarter=QuarterlyCount(year=2023, quarter=2, count=15, label="2023-Q2"),
            mean_quarterly=12.5,
            std_quarterly=3.5,
            meta=make_meta(),
        )
        result = runner.invoke(app, ["timeline", "etomidate", "anhedonia"])
        assert result.exit_code == 0
        assert "ETOMIDATE" in result.output
        assert "2023-Q1" in result.output

    @patch("hypokrates.sync.stats")
    def test_timeline_json(self, mock_stats: MagicMock) -> None:
        mock_stats.signal_timeline.return_value = TimelineResult(
            drug="d",
            event="e",
            total_reports=0,
            meta=make_meta(),
        )
        result = runner.invoke(app, ["timeline", "d", "e", "-f", "json"])
        assert result.exit_code == 0
        assert '"drug"' in result.output
