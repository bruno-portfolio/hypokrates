"""Contratos formais via Protocol — interfaces para módulos plugáveis."""

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol, runtime_checkable

if TYPE_CHECKING:
    from hypokrates.evidence.models import EvidenceBlock
    from hypokrates.stats.models import SignalResult


@runtime_checkable
class SignalDetector(Protocol):
    """Qualquer módulo que detecta sinais estatísticos."""

    async def signal(
        self,
        drug: str,
        event: str,
        *,
        use_cache: bool = True,
    ) -> SignalResult:
        """Detecta sinal para par droga-evento."""
        ...


@runtime_checkable
class EvidenceProvider(Protocol):
    """Qualquer módulo que fornece dados com proveniência."""

    async def fetch_with_evidence(
        self,
        query: str,
        *,
        use_cache: bool = True,
    ) -> EvidenceBlock:
        """Busca dados com proveniência completa."""
        ...
