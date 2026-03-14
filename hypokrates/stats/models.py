"""Modelos para detecção de sinais estatísticos."""

from __future__ import annotations

from pydantic import BaseModel, Field

from hypokrates.models import MetaInfo  # noqa: TC001 — Pydantic needs at runtime


class ContingencyTable(BaseModel):
    """Tabela de contingência 2x2 para análise de desproporcionalidade.

    Attributes:
        a: Reports com droga D E evento E.
        b: Reports com droga D SEM evento E.
        c: Reports SEM droga D COM evento E.
        d: Reports SEM droga D SEM evento E.
    """

    a: int = Field(description="drug + event")
    b: int = Field(description="drug + not event")
    c: int = Field(description="not drug + event")
    d: int = Field(description="not drug + not event")

    @property
    def n(self) -> int:
        """Total de reports (a + b + c + d)."""
        return self.a + self.b + self.c + self.d


class DisproportionalityResult(BaseModel):
    """Resultado de uma medida individual (PRR, ROR ou IC)."""

    measure: str = Field(description="Nome da medida: PRR, ROR ou IC")
    value: float = Field(description="Ponto estimado")
    ci_lower: float = Field(description="Intervalo de confiança 95% — limite inferior")
    ci_upper: float = Field(description="Intervalo de confiança 95% — limite superior")
    significant: bool = Field(
        description="ci_lower > 1.0 (PRR/ROR) ou ci_lower > 0 (IC)"
    )


class SignalResult(BaseModel):
    """Resultado completo de detecção de sinal para um par droga-evento.

    signal_detected é uma heurística de conveniência (>= 2 medidas
    significantes), NÃO uma verdade clínica. Cada agência usa critérios
    diferentes (FDA: EBGM/GPS, EMA: PRR, Uppsala: IC). O campo existe
    para triagem rápida — o usuário deve avaliar as medidas individuais
    (prr, ror, ic) para decisão clínica.
    """

    drug: str
    event: str
    table: ContingencyTable
    prr: DisproportionalityResult
    ror: DisproportionalityResult
    ic: DisproportionalityResult = Field(
        description="IC simplified (não BCPNN completo)"
    )
    signal_detected: bool = Field(
        description="Heurística: >= 2 medidas significantes"
    )
    meta: MetaInfo
