"""Testes para hypokrates.evidence.builder."""

from __future__ import annotations

from hypokrates.evidence.builder import (
    _FAERS_LIMITATIONS,
    build_evidence,
    build_faers_evidence,
)
from hypokrates.evidence.models import EvidenceBlock, Limitation
from tests.helpers import make_meta

_EVIDENCE_META_KW = {"source": "OpenFDA/FAERS", "total": 42, "query": {"drug": "propofol"}}


class TestBuildEvidence:
    """Testes para build_evidence."""

    def test_from_meta_info(self) -> None:
        meta = make_meta(**_EVIDENCE_META_KW)
        block = build_evidence(meta, {"events": []})
        assert isinstance(block, EvidenceBlock)
        assert block.source == "OpenFDA/FAERS"
        assert block.query == {"drug": "propofol"}
        assert block.retrieved_at == meta.retrieved_at

    def test_custom_limitations(self) -> None:
        meta = make_meta(**_EVIDENCE_META_KW)
        lims = [Limitation.INDICATION_BIAS, Limitation.NOTORIETY_BIAS]
        block = build_evidence(meta, {}, limitations=lims)
        assert block.limitations == lims

    def test_methodology_preserved(self) -> None:
        meta = make_meta(**_EVIDENCE_META_KW)
        block = build_evidence(meta, {}, methodology="PRR via Rothman-Greenland CI")
        assert block.methodology == "PRR via Rothman-Greenland CI"

    def test_confidence_preserved(self) -> None:
        meta = make_meta(**_EVIDENCE_META_KW)
        block = build_evidence(meta, {}, confidence="signal_detected")
        assert block.confidence == "signal_detected"

    def test_empty_limitations_by_default(self) -> None:
        meta = make_meta(**_EVIDENCE_META_KW)
        block = build_evidence(meta, {})
        assert block.limitations == []

    def test_api_version_from_meta(self) -> None:
        meta = make_meta(**_EVIDENCE_META_KW, api_version="v2.1")
        block = build_evidence(meta, {})
        assert block.source_version == "v2.1"


class TestBuildFAERSEvidence:
    """Testes para build_faers_evidence."""

    def test_default_limitations(self) -> None:
        meta = make_meta(**_EVIDENCE_META_KW)
        block = build_faers_evidence(meta, {})
        assert len(block.limitations) == 5
        assert block.limitations == _FAERS_LIMITATIONS

    def test_disclaimer_default(self) -> None:
        meta = make_meta(**_EVIDENCE_META_KW)
        block = build_faers_evidence(meta, {})
        assert block.disclaimer

    def test_confidence_passed_through(self) -> None:
        meta = make_meta(**_EVIDENCE_META_KW)
        block = build_faers_evidence(meta, {}, confidence="no_signal")
        assert block.confidence == "no_signal"

    def test_methodology_passed_through(self) -> None:
        meta = make_meta(**_EVIDENCE_META_KW)
        block = build_faers_evidence(meta, {}, methodology="ROR via Woolf")
        assert block.methodology == "ROR via Woolf"
