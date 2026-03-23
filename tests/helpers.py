"""Helpers para testes — builders tipados, mock HTTP, assertion helpers de domínio."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import httpx
import respx

from hypokrates.evidence.models import EvidenceBlock
from hypokrates.faers.models import FAERSReport, FAERSResult
from hypokrates.models import AdverseEvent, MetaInfo
from hypokrates.pubmed.models import PubMedArticle
from hypokrates.stats.models import ContingencyTable, DisproportionalityResult, SignalResult

GOLDEN_DATA = Path(__file__).parent / "golden_data"


def load_golden(source: str, filename: str) -> dict[str, Any]:
    """Carrega golden data de testes."""
    path = GOLDEN_DATA / source / filename
    return json.loads(path.read_text())  # type: ignore[no-any-return]


def load_golden_text(source: str, filename: str) -> str:
    """Carrega golden data como texto (XML, CSV, etc.)."""
    path = GOLDEN_DATA / source / filename
    return path.read_text(encoding="utf-8")


def mock_openfda_response(
    data: dict[str, Any],
    *,
    status_code: int = 200,
) -> respx.MockRouter:
    """Configura mock para resposta do OpenFDA."""
    router = respx.MockRouter()
    router.get(url__startswith="https://api.fda.gov/drug/event.json").mock(
        return_value=httpx.Response(
            status_code=status_code,
            json=data,
        )
    )
    return router


# ---------------------------------------------------------------------------
# Builders tipados — criam estruturas OpenFDA raw sem repetir golden data
# ---------------------------------------------------------------------------


def make_raw_reaction(
    *,
    term: str = "HYPOTENSION",
    outcome: str | None = "1",
    version: str | None = "27.1",
) -> dict[str, Any]:
    """Builder para reação raw OpenFDA."""
    r: dict[str, Any] = {"reactionmeddrapt": term}
    if outcome is not None:
        r["reactionoutcome"] = outcome
    if version is not None:
        r["reactionmeddraversionpt"] = version
    return r


def make_raw_drug(
    *,
    name: str = "PROPOFOL",
    role: str = "1",
    route: str | None = "065",
    dose: str | None = "200 MG, IV",
    indication: str | None = "ANAESTHESIA",
    generic_names: list[str] | None = None,
    brand_names: list[str] | None = None,
    include_openfda: bool = True,
) -> dict[str, Any]:
    """Builder para droga raw OpenFDA."""
    d: dict[str, Any] = {
        "drugcharacterization": role,
        "medicinalproduct": name,
    }
    if route is not None:
        d["drugadministrationroute"] = route
    if dose is not None:
        d["drugdosagetext"] = dose
    if indication is not None:
        d["drugindication"] = indication
    if include_openfda:
        openfda: dict[str, Any] = {}
        openfda["generic_name"] = generic_names if generic_names is not None else [name]
        if brand_names is not None:
            openfda["brand_name"] = brand_names
        d["openfda"] = openfda
    return d


def make_raw_patient(
    *,
    age: str | None = "65",
    age_unit: str | None = "801",
    sex: str | None = "1",
    weight: str | None = "80.0",
    reactions: list[dict[str, Any]] | None = None,
    drugs: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Builder para paciente raw OpenFDA."""
    p: dict[str, Any] = {}
    if age is not None:
        p["patientonsetage"] = age
    if age_unit is not None:
        p["patientonsetageunit"] = age_unit
    if sex is not None:
        p["patientsex"] = sex
    if weight is not None:
        p["patientweight"] = weight
    p["reaction"] = reactions if reactions is not None else [make_raw_reaction()]
    p["drug"] = drugs if drugs is not None else [make_raw_drug()]
    return p


def make_raw_report(
    *,
    report_id: str = "TEST001",
    serious: str = "1",
    country: str = "US",
    patient: dict[str, Any] | None = None,
    receive_date: str | None = "20240101",
    receipt_date: str | None = "20240105",
    qualification: str | None = "1",
    seriousness_flags: dict[str, str] | None = None,
) -> dict[str, Any]:
    """Builder para report raw OpenFDA."""
    r: dict[str, Any] = {
        "safetyreportid": report_id,
        "serious": serious,
        "occurcountry": country,
        "patient": patient if patient is not None else make_raw_patient(),
    }
    if receive_date is not None:
        r["receivedate"] = receive_date
    if receipt_date is not None:
        r["receiptdate"] = receipt_date
    if qualification is not None:
        r["primarysource"] = {"qualification": qualification}
    if seriousness_flags is not None:
        for flag_key, flag_val in seriousness_flags.items():
            r[flag_key] = flag_val
    return r


# ---------------------------------------------------------------------------
# Assertion helpers de domínio
# ---------------------------------------------------------------------------


def assert_clinical_field(
    report: FAERSReport,
    field: str,
    expected: object,
    msg: str = "",
) -> None:
    """Valida campo clínico de um FAERSReport com mensagem descritiva."""
    actual = getattr(report, field, None)
    if actual is None and "." in field:
        # Support dotted paths like "patient.age"
        parts = field.split(".")
        obj: Any = report
        for part in parts:
            obj = getattr(obj, part, None)
        actual = obj
    context = msg or f"Campo clínico {field!r}"
    assert actual == expected, f"{context}: esperado {expected!r}, obteve {actual!r}"


def assert_meta_complete(meta: MetaInfo) -> None:
    """Verifica que MetaInfo tem todos os campos obrigatórios preenchidos."""
    assert meta.source, "MetaInfo.source vazio"
    assert meta.retrieved_at is not None, "MetaInfo.retrieved_at ausente"
    assert meta.disclaimer, "MetaInfo.disclaimer vazio"
    assert isinstance(meta.total_results, int), "MetaInfo.total_results não é int"
    assert isinstance(meta.query, dict), "MetaInfo.query não é dict"


# ---------------------------------------------------------------------------
# Shared test factories — MetaInfo, SignalResult, EvidenceBlock, FAERSResult
# ---------------------------------------------------------------------------


def make_meta(*, source: str = "test", total: int = 0, **kwargs: Any) -> MetaInfo:
    """Factory para MetaInfo de teste."""
    return MetaInfo(source=source, total_results=total, retrieved_at=datetime.now(UTC), **kwargs)


def make_signal(
    *,
    drug: str = "propofol",
    event: str = "TEST",
    a: int = 100,
    prr: float = 2.0,
    prr_lci: float | None = None,
    ror_lci: float | None = None,
    detected: bool = True,
) -> SignalResult:
    """Factory para SignalResult de teste.

    prr_lci/ror_lci permitem override dos CI lower bounds (usado em testes de score).
    """
    _prr_lci = prr_lci if prr_lci is not None else prr * 0.75
    _ror_lci = ror_lci if ror_lci is not None else (prr * 1.05) * 0.75
    return SignalResult(
        drug=drug,
        event=event,
        table=ContingencyTable(a=a, b=900, c=50, d=9000),
        prr=DisproportionalityResult(
            measure="PRR",
            value=prr,
            ci_lower=_prr_lci,
            ci_upper=prr * 1.3,
            significant=detected,
        ),
        ror=DisproportionalityResult(
            measure="ROR",
            value=prr * 1.05,
            ci_lower=_ror_lci,
            ci_upper=prr * 1.4,
            significant=detected,
        ),
        ic=DisproportionalityResult(
            measure="IC",
            value=1.0,
            ci_lower=0.5,
            ci_upper=1.5,
            significant=detected,
        ),
        ebgm=DisproportionalityResult(
            measure="EBGM",
            value=2.0,
            ci_lower=1.5,
            ci_upper=2.5,
            significant=detected,
        ),
        signal_detected=detected,
        meta=make_meta(),
    )


def make_evidence(*, source: str = "test", **kwargs: Any) -> EvidenceBlock:
    """Factory para EvidenceBlock de teste."""
    return EvidenceBlock(source=source, retrieved_at=datetime.now(UTC), **kwargs)


def make_events(terms: list[str]) -> FAERSResult:
    """Factory para FAERSResult de teste com eventos."""
    return FAERSResult(
        events=[AdverseEvent(term=t, count=100 - i) for i, t in enumerate(terms)],
        meta=make_meta(),
    )


def make_article(
    pmid: str = "12345",
    title: str = "Test Article",
    *,
    authors: list[str] | None = None,
    journal: str | None = "J Clin Pharmacol",
    pub_date: str | None = "2024",
    doi: str | None = None,
) -> PubMedArticle:
    """Factory para PubMedArticle de teste."""
    return PubMedArticle(
        pmid=pmid,
        title=title,
        authors=authors or ["Smith John"],
        journal=journal,
        pub_date=pub_date,
        doi=doi,
    )
