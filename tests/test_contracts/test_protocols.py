"""Testes para hypokrates.contracts.protocols."""

from __future__ import annotations

from typing import Protocol

from hypokrates.contracts.protocols import EvidenceProvider, SignalDetector


class TestProtocols:
    """Testes para Protocol classes."""

    def test_signal_detector_is_protocol(self) -> None:
        assert issubclass(SignalDetector, Protocol)

    def test_evidence_provider_is_protocol(self) -> None:
        assert issubclass(EvidenceProvider, Protocol)

    def test_signal_detector_runtime_checkable(self) -> None:
        """isinstance() funciona com SignalDetector."""
        assert getattr(SignalDetector, "_is_runtime_protocol", False)

    def test_evidence_provider_runtime_checkable(self) -> None:
        assert getattr(EvidenceProvider, "_is_runtime_protocol", False)

    def test_signal_detector_has_signal_method(self) -> None:
        """Protocol define método signal."""
        assert hasattr(SignalDetector, "signal")

    def test_evidence_provider_has_fetch_method(self) -> None:
        assert hasattr(EvidenceProvider, "fetch_with_evidence")
