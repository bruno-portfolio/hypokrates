"""Testes para hypokrates.scan.class_compare."""

from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import AsyncMock, patch

import pytest

from hypokrates.exceptions import ValidationError
from hypokrates.faers.models import FAERSResult
from hypokrates.models import AdverseEvent, MetaInfo
from hypokrates.scan.class_compare import compare_class
from hypokrates.scan.models import EventClassification
from hypokrates.stats.models import ContingencyTable, DisproportionalityResult, SignalResult

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_meta() -> MetaInfo:
    return MetaInfo(source="test", retrieved_at=datetime.now(UTC))


def _make_signal(
    drug: str,
    event: str,
    *,
    prr: float = 2.0,
    detected: bool = True,
) -> SignalResult:
    return SignalResult(
        drug=drug,
        event=event,
        table=ContingencyTable(a=100, b=900, c=50, d=9000),
        prr=DisproportionalityResult(
            measure="PRR", value=prr, ci_lower=prr * 0.7, ci_upper=prr * 1.3, significant=detected
        ),
        ror=DisproportionalityResult(
            measure="ROR",
            value=prr * 1.1,
            ci_lower=prr * 0.8,
            ci_upper=prr * 1.4,
            significant=detected,
        ),
        ic=DisproportionalityResult(
            measure="IC", value=1.0, ci_lower=0.5, ci_upper=1.5, significant=detected
        ),
        signal_detected=detected,
        meta=_make_meta(),
    )


def _make_events(terms: list[str]) -> FAERSResult:
    return FAERSResult(
        events=[AdverseEvent(term=t, count=100 - i) for i, t in enumerate(terms)],
        meta=_make_meta(),
    )


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


@patch("hypokrates.scan.class_compare.stats_api.signal")
@patch("hypokrates.scan.class_compare.faers_api.resolve_drug_field")
@patch("hypokrates.scan.class_compare.FAERSClient")
@patch("hypokrates.scan.class_compare.faers_api.top_events")
async def test_class_effect(
    mock_top: AsyncMock,
    mock_client_cls: AsyncMock,
    mock_resolve: AsyncMock,
    mock_signal: AsyncMock,
) -> None:
    """3 drogas, todas com signal_detected para mesmo evento → class_effect."""
    drugs = ["drug_a", "drug_b", "drug_c"]

    mock_top.side_effect = [
        _make_events(["NAUSEA"]),
        _make_events(["NAUSEA"]),
        _make_events(["NAUSEA"]),
    ]

    client_instance = AsyncMock()
    client_instance.fetch_total = AsyncMock(return_value=10000)
    client_instance.close = AsyncMock()
    mock_client_cls.return_value = client_instance

    mock_resolve.return_value = 'patient.drug.openfda.generic_name.exact:"drug_a"'

    async def _signal_side_effect(drug: str, event: str, **kwargs: object) -> SignalResult:
        return _make_signal(drug, event, prr=2.0, detected=True)

    mock_signal.side_effect = _signal_side_effect

    result = await compare_class(drugs, top_n=5)

    assert result.total_events == 1
    assert result.class_effect_count == 1
    assert result.items[0].classification == EventClassification.CLASS_EFFECT
    assert result.items[0].event == "NAUSEA AND VOMITING"  # canonical MedDRA
    assert len(result.items[0].drugs_with_signal) == 3


@patch("hypokrates.scan.class_compare.stats_api.signal")
@patch("hypokrates.scan.class_compare.faers_api.resolve_drug_field")
@patch("hypokrates.scan.class_compare.FAERSClient")
@patch("hypokrates.scan.class_compare.faers_api.top_events")
async def test_drug_specific(
    mock_top: AsyncMock,
    mock_client_cls: AsyncMock,
    mock_resolve: AsyncMock,
    mock_signal: AsyncMock,
) -> None:
    """3 drogas, apenas 1 com signal_detected → drug_specific."""
    drugs = ["drug_a", "drug_b", "drug_c"]

    mock_top.side_effect = [
        _make_events(["RASH"]),
        _make_events(["HEADACHE"]),
        _make_events(["HEADACHE"]),
    ]

    client_instance = AsyncMock()
    client_instance.fetch_total = AsyncMock(return_value=10000)
    client_instance.close = AsyncMock()
    mock_client_cls.return_value = client_instance
    mock_resolve.return_value = 'patient.drug.openfda.generic_name.exact:"drug_a"'

    async def _signal_side_effect(drug: str, event: str, **kwargs: object) -> SignalResult:
        if event == "RASH" and drug == "drug_a":
            return _make_signal(drug, event, prr=5.0, detected=True)
        return _make_signal(drug, event, prr=0.8, detected=False)

    mock_signal.side_effect = _signal_side_effect

    result = await compare_class(drugs, top_n=5)

    rash_item = next(it for it in result.items if it.event == "RASH")
    assert rash_item.classification == EventClassification.DRUG_SPECIFIC
    assert rash_item.drugs_with_signal == ["drug_a"]


@patch("hypokrates.scan.class_compare.stats_api.signal")
@patch("hypokrates.scan.class_compare.faers_api.resolve_drug_field")
@patch("hypokrates.scan.class_compare.FAERSClient")
@patch("hypokrates.scan.class_compare.faers_api.top_events")
async def test_differential_by_count(
    mock_top: AsyncMock,
    mock_client_cls: AsyncMock,
    mock_resolve: AsyncMock,
    mock_signal: AsyncMock,
) -> None:
    """2 de 3 com signal → differential (abaixo do threshold de 75%)."""
    drugs = ["drug_a", "drug_b", "drug_c"]

    mock_top.side_effect = [
        _make_events(["DIZZINESS"]),
        _make_events(["DIZZINESS"]),
        _make_events(["DIZZINESS"]),
    ]

    client_instance = AsyncMock()
    client_instance.fetch_total = AsyncMock(return_value=10000)
    client_instance.close = AsyncMock()
    mock_client_cls.return_value = client_instance
    mock_resolve.return_value = 'patient.drug.openfda.generic_name.exact:"drug_a"'

    async def _signal_side_effect(drug: str, event: str, **kwargs: object) -> SignalResult:
        if drug in ("drug_a", "drug_b"):
            return _make_signal(drug, event, prr=3.0, detected=True)
        return _make_signal(drug, event, prr=0.5, detected=False)

    mock_signal.side_effect = _signal_side_effect

    # threshold 0.75 → 2/3 = 0.666 < 0.75 → differential
    result = await compare_class(drugs, top_n=5, class_threshold=0.75)

    assert result.items[0].classification == EventClassification.DIFFERENTIAL
    assert len(result.items[0].drugs_with_signal) == 2


@patch("hypokrates.scan.class_compare.stats_api.signal")
@patch("hypokrates.scan.class_compare.faers_api.resolve_drug_field")
@patch("hypokrates.scan.class_compare.FAERSClient")
@patch("hypokrates.scan.class_compare.faers_api.top_events")
async def test_differential_by_outlier(
    mock_top: AsyncMock,
    mock_client_cls: AsyncMock,
    mock_resolve: AsyncMock,
    mock_signal: AsyncMock,
) -> None:
    """3 com signal mas 1 PRR >> outras → differential (outlier)."""
    drugs = ["drug_a", "drug_b", "drug_c"]

    mock_top.side_effect = [
        _make_events(["HEPATOTOXICITY"]),
        _make_events(["HEPATOTOXICITY"]),
        _make_events(["HEPATOTOXICITY"]),
    ]

    client_instance = AsyncMock()
    client_instance.fetch_total = AsyncMock(return_value=10000)
    client_instance.close = AsyncMock()
    mock_client_cls.return_value = client_instance
    mock_resolve.return_value = 'patient.drug.openfda.generic_name.exact:"drug_a"'

    async def _signal_side_effect(drug: str, event: str, **kwargs: object) -> SignalResult:
        prr_map = {"drug_a": 30.0, "drug_b": 2.0, "drug_c": 2.5}
        return _make_signal(drug, event, prr=prr_map[drug], detected=True)

    mock_signal.side_effect = _signal_side_effect

    result = await compare_class(drugs, top_n=5, outlier_factor=3.0)

    item = result.items[0]
    assert item.classification == EventClassification.DIFFERENTIAL
    assert item.outlier_drug == "drug_a"
    assert item.outlier_factor is not None
    assert item.outlier_factor > 3.0


@patch("hypokrates.scan.class_compare.faers_api.top_events")
async def test_empty_events(mock_top: AsyncMock) -> None:
    """Sem eventos → result vazio."""
    drugs = ["drug_a", "drug_b"]

    mock_top.side_effect = [
        FAERSResult(events=[], meta=_make_meta()),
        FAERSResult(events=[], meta=_make_meta()),
    ]

    result = await compare_class(drugs, top_n=5)

    assert result.total_events == 0
    assert result.items == []


@patch("hypokrates.scan.class_compare.stats_api.signal")
@patch("hypokrates.scan.class_compare.faers_api.resolve_drug_field")
@patch("hypokrates.scan.class_compare.FAERSClient")
@patch("hypokrates.scan.class_compare.faers_api.top_events")
async def test_operational_filtered(
    mock_top: AsyncMock,
    mock_client_cls: AsyncMock,
    mock_resolve: AsyncMock,
    mock_signal: AsyncMock,
) -> None:
    """Termos operacionais excluídos por padrão."""
    drugs = ["drug_a", "drug_b"]

    mock_top.side_effect = [
        _make_events(["OFF LABEL USE", "RASH"]),
        _make_events(["DRUG INEFFECTIVE", "RASH"]),
    ]

    client_instance = AsyncMock()
    client_instance.fetch_total = AsyncMock(return_value=10000)
    client_instance.close = AsyncMock()
    mock_client_cls.return_value = client_instance
    mock_resolve.return_value = 'patient.drug.openfda.generic_name.exact:"drug_a"'

    async def _signal_side_effect(drug: str, event: str, **kwargs: object) -> SignalResult:
        return _make_signal(drug, event, prr=2.0, detected=True)

    mock_signal.side_effect = _signal_side_effect

    result = await compare_class(drugs, top_n=5)

    event_names = [it.event for it in result.items]
    assert "OFF LABEL USE" not in event_names
    assert "DRUG INEFFECTIVE" not in event_names
    assert "RASH" in event_names


@patch("hypokrates.scan.class_compare.stats_api.signal")
@patch("hypokrates.scan.class_compare.faers_api.resolve_drug_field")
@patch("hypokrates.scan.class_compare.FAERSClient")
@patch("hypokrates.scan.class_compare.faers_api.top_events")
async def test_meddra_dedup(
    mock_top: AsyncMock,
    mock_client_cls: AsyncMock,
    mock_resolve: AsyncMock,
    mock_signal: AsyncMock,
) -> None:
    """Sinônimos MedDRA canonicalizados na união de eventos."""
    drugs = ["drug_a", "drug_b"]

    # ANAPHYLACTIC REACTION e ANAPHYLACTIC SHOCK → canonical ANAPHYLAXIS
    mock_top.side_effect = [
        _make_events(["ANAPHYLACTIC REACTION"]),
        _make_events(["ANAPHYLACTIC SHOCK"]),
    ]

    client_instance = AsyncMock()
    client_instance.fetch_total = AsyncMock(return_value=10000)
    client_instance.close = AsyncMock()
    mock_client_cls.return_value = client_instance
    mock_resolve.return_value = 'patient.drug.openfda.generic_name.exact:"drug_a"'

    async def _signal_side_effect(drug: str, event: str, **kwargs: object) -> SignalResult:
        return _make_signal(drug, event, prr=5.0, detected=True)

    mock_signal.side_effect = _signal_side_effect

    result = await compare_class(drugs, top_n=5)

    event_names = [it.event for it in result.items]
    # Apenas 1 evento canônico, não 2 aliases separados
    assert len(event_names) == 1
    assert "ANAPHYLAXIS" in event_names


async def test_validation_min_drugs() -> None:
    """< 2 drogas → ValidationError."""
    with pytest.raises(ValidationError, match="at least 2"):
        await compare_class(["only_one"])

    with pytest.raises(ValidationError, match="at least 2"):
        await compare_class([])
