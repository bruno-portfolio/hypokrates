"""Testes para hypokrates.scan.api."""

from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import AsyncMock, patch

import pytest

from hypokrates.cross.models import HypothesisClassification, HypothesisResult
from hypokrates.faers.models import FAERSResult
from hypokrates.pubmed.models import PubMedArticle
from hypokrates.scan.api import _score, scan_drug
from hypokrates.scan.constants import LABEL_IN_MULTIPLIER, LABEL_NOT_IN_MULTIPLIER
from hypokrates.stats.models import ContingencyTable, DisproportionalityResult, SignalResult
from tests.helpers import make_events, make_evidence, make_meta, make_signal


def _make_hypothesis_result(
    event: str,
    classification: HypothesisClassification,
    *,
    signal_detected: bool = True,
    lit_count: int = 0,
    prr_lci: float = 1.5,
    ror_lci: float = 1.6,
    in_label: bool | None = None,
    active_trials: int | None = None,
) -> HypothesisResult:
    """Factory para HypothesisResult de teste."""
    return HypothesisResult(
        drug="propofol",
        event=event,
        classification=classification,
        signal=make_signal(prr_lci=prr_lci, ror_lci=ror_lci, detected=signal_detected),
        literature_count=lit_count,
        articles=[PubMedArticle(pmid="123", title="Test")] if lit_count > 0 else [],
        evidence=make_evidence(),
        summary=f"{classification.value}: propofol + {event}",
        thresholds_used={"novel_max": 0, "emerging_max": 5},
        in_label=in_label,
        active_trials=active_trials,
    )


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


@patch("hypokrates.scan.api.cross_api.hypothesis")
@patch("hypokrates.scan.api.faers_api.top_events")
async def test_scan_basic(
    mock_top_events: AsyncMock,
    mock_hypothesis: AsyncMock,
) -> None:
    """3 eventos, classificações mistas → resultado correto."""
    mock_top_events.return_value = make_events(["NAUSEA", "HEADACHE", "RASH"])

    mock_hypothesis.side_effect = [
        _make_hypothesis_result("NAUSEA", HypothesisClassification.NOVEL_HYPOTHESIS),
        _make_hypothesis_result(
            "HEADACHE",
            HypothesisClassification.KNOWN_ASSOCIATION,
            lit_count=10,
        ),
        _make_hypothesis_result("RASH", HypothesisClassification.EMERGING_SIGNAL, lit_count=3),
    ]

    result = await scan_drug("propofol", top_n=3)

    assert result.drug == "propofol"
    assert result.total_scanned == 3
    assert result.novel_count == 1
    assert result.known_count == 1
    assert result.emerging_count == 1
    assert result.no_signal_count == 0
    assert result.failed_count == 0
    assert len(result.items) == 3


@patch("hypokrates.scan.api.cross_api.hypothesis")
@patch("hypokrates.scan.api.faers_api.top_events")
async def test_scan_scoring_order(
    mock_top_events: AsyncMock,
    mock_hypothesis: AsyncMock,
) -> None:
    """Novel com sinal forte > emerging com sinal fraco."""
    mock_top_events.return_value = make_events(["A", "B"])

    mock_hypothesis.side_effect = [
        _make_hypothesis_result(
            "A",
            HypothesisClassification.EMERGING_SIGNAL,
            lit_count=3,
            prr_lci=0.5,
            ror_lci=0.6,
        ),
        _make_hypothesis_result(
            "B",
            HypothesisClassification.NOVEL_HYPOTHESIS,
            prr_lci=3.0,
            ror_lci=3.5,
        ),
    ]

    result = await scan_drug("propofol", top_n=2)

    assert result.items[0].event == "B"  # novel com sinal forte
    assert result.items[1].event == "A"  # emerging com sinal fraco
    assert result.items[0].rank == 1
    assert result.items[1].rank == 2
    assert result.items[0].score > result.items[1].score


@patch("hypokrates.scan.api.cross_api.hypothesis")
@patch("hypokrates.scan.api.faers_api.top_events")
async def test_scan_filter_no_signal(
    mock_top_events: AsyncMock,
    mock_hypothesis: AsyncMock,
) -> None:
    """include_no_signal=False filtra corretamente."""
    mock_top_events.return_value = make_events(["A", "B"])

    mock_hypothesis.side_effect = [
        _make_hypothesis_result(
            "A",
            HypothesisClassification.NOVEL_HYPOTHESIS,
        ),
        _make_hypothesis_result(
            "B",
            HypothesisClassification.NO_SIGNAL,
            signal_detected=False,
        ),
    ]

    result = await scan_drug("propofol", top_n=2, include_no_signal=False)

    assert len(result.items) == 1
    assert result.items[0].event == "A"
    assert result.no_signal_count == 1  # contado mesmo que filtrado


@patch("hypokrates.scan.api.cross_api.hypothesis")
@patch("hypokrates.scan.api.faers_api.top_events")
async def test_scan_include_no_signal(
    mock_top_events: AsyncMock,
    mock_hypothesis: AsyncMock,
) -> None:
    """include_no_signal=True inclui tudo."""
    mock_top_events.return_value = make_events(["A", "B"])

    mock_hypothesis.side_effect = [
        _make_hypothesis_result("A", HypothesisClassification.NOVEL_HYPOTHESIS),
        _make_hypothesis_result(
            "B",
            HypothesisClassification.NO_SIGNAL,
            signal_detected=False,
        ),
    ]

    result = await scan_drug("propofol", top_n=2, include_no_signal=True)

    assert len(result.items) == 2


@patch("hypokrates.scan.api.cross_api.hypothesis")
@patch("hypokrates.scan.api.faers_api.top_events")
async def test_scan_empty_events(
    mock_top_events: AsyncMock,
    mock_hypothesis: AsyncMock,
) -> None:
    """Droga sem eventos FAERS → ScanResult vazio."""
    mock_top_events.return_value = FAERSResult(events=[], meta=make_meta())

    result = await scan_drug("unknowndrug", top_n=10)

    assert result.total_scanned == 0
    assert result.items == []
    mock_hypothesis.assert_not_called()


@patch("hypokrates.scan.api.cross_api.hypothesis")
@patch("hypokrates.scan.api.faers_api.top_events")
async def test_scan_partial_failure(
    mock_top_events: AsyncMock,
    mock_hypothesis: AsyncMock,
) -> None:
    """1 de 3 hypothesis falha → 2 items + failed_count=1."""
    mock_top_events.return_value = make_events(["A", "B", "C"])

    mock_hypothesis.side_effect = [
        _make_hypothesis_result("A", HypothesisClassification.NOVEL_HYPOTHESIS),
        RuntimeError("API error"),
        _make_hypothesis_result("C", HypothesisClassification.EMERGING_SIGNAL, lit_count=2),
    ]

    result = await scan_drug("propofol", top_n=3)

    assert len(result.items) == 2
    assert result.failed_count == 1
    assert "B" in result.skipped_events


@patch("hypokrates.scan.api.cross_api.hypothesis")
@patch("hypokrates.scan.api.faers_api.top_events")
async def test_scan_all_fail(
    mock_top_events: AsyncMock,
    mock_hypothesis: AsyncMock,
) -> None:
    """Todos falham → items vazio, failed_count=N."""
    mock_top_events.return_value = make_events(["A", "B"])

    mock_hypothesis.side_effect = [
        RuntimeError("error1"),
        RuntimeError("error2"),
    ]

    result = await scan_drug("propofol", top_n=2)

    assert result.items == []
    assert result.failed_count == 2
    assert result.total_scanned == 2


@patch("hypokrates.scan.api.cross_api.hypothesis")
@patch("hypokrates.scan.api.faers_api.top_events")
async def test_scan_ranking(
    mock_top_events: AsyncMock,
    mock_hypothesis: AsyncMock,
) -> None:
    """Ranks atribuídos corretamente (1, 2, 3...)."""
    mock_top_events.return_value = make_events(["A", "B", "C"])

    mock_hypothesis.side_effect = [
        _make_hypothesis_result(
            "A",
            HypothesisClassification.KNOWN_ASSOCIATION,
            lit_count=10,
            prr_lci=1.0,
            ror_lci=1.0,
        ),
        _make_hypothesis_result(
            "B",
            HypothesisClassification.NOVEL_HYPOTHESIS,
            prr_lci=2.0,
            ror_lci=2.0,
        ),
        _make_hypothesis_result(
            "C",
            HypothesisClassification.EMERGING_SIGNAL,
            lit_count=3,
            prr_lci=1.5,
            ror_lci=1.5,
        ),
    ]

    result = await scan_drug("propofol", top_n=3)

    ranks = [item.rank for item in result.items]
    assert ranks == [1, 2, 3]
    # Verify scores are descending
    scores = [item.score for item in result.items]
    assert scores == sorted(scores, reverse=True)


@patch("hypokrates.scan.api.cross_api.hypothesis")
@patch("hypokrates.scan.api.faers_api.top_events")
async def test_scan_counts(
    mock_top_events: AsyncMock,
    mock_hypothesis: AsyncMock,
) -> None:
    """Contadores de classificação corretos."""
    mock_top_events.return_value = make_events(["A", "B", "C", "D"])

    mock_hypothesis.side_effect = [
        _make_hypothesis_result("A", HypothesisClassification.NOVEL_HYPOTHESIS),
        _make_hypothesis_result("B", HypothesisClassification.EMERGING_SIGNAL, lit_count=3),
        _make_hypothesis_result("C", HypothesisClassification.KNOWN_ASSOCIATION, lit_count=10),
        _make_hypothesis_result("D", HypothesisClassification.NO_SIGNAL, signal_detected=False),
    ]

    result = await scan_drug("propofol", top_n=4, include_no_signal=True)

    assert result.novel_count == 1
    assert result.emerging_count == 1
    assert result.known_count == 1
    assert result.no_signal_count == 1
    assert result.failed_count == 0


@patch("hypokrates.scan.api.cross_api.hypothesis")
@patch("hypokrates.scan.api.faers_api.top_events")
async def test_scan_on_progress_callback(
    mock_top_events: AsyncMock,
    mock_hypothesis: AsyncMock,
) -> None:
    """Callback on_progress é chamado para cada evento."""
    mock_top_events.return_value = make_events(["A", "B"])

    mock_hypothesis.side_effect = [
        _make_hypothesis_result("A", HypothesisClassification.NOVEL_HYPOTHESIS),
        _make_hypothesis_result("B", HypothesisClassification.KNOWN_ASSOCIATION, lit_count=10),
    ]

    progress_calls: list[tuple[int, int, str]] = []

    def on_progress(completed: int, total: int, event: str) -> None:
        progress_calls.append((completed, total, event))

    await scan_drug("propofol", top_n=2, on_progress=on_progress)

    assert len(progress_calls) == 2
    # All calls should have total=2
    assert all(t == 2 for _, t, _ in progress_calls)


@patch("hypokrates.scan.api.cross_api.hypothesis")
@patch("hypokrates.scan.api.faers_api.top_events")
async def test_scan_labeled_count(
    mock_top_events: AsyncMock,
    mock_hypothesis: AsyncMock,
) -> None:
    """labeled_count conta eventos in_label=True."""
    mock_top_events.return_value = make_events(["A", "B", "C"])

    mock_hypothesis.side_effect = [
        _make_hypothesis_result("A", HypothesisClassification.NOVEL_HYPOTHESIS, in_label=True),
        _make_hypothesis_result(
            "B", HypothesisClassification.EMERGING_SIGNAL, lit_count=3, in_label=False
        ),
        _make_hypothesis_result(
            "C", HypothesisClassification.KNOWN_ASSOCIATION, lit_count=10, in_label=True
        ),
    ]

    result = await scan_drug("propofol", top_n=3)

    assert result.labeled_count == 2


@patch("hypokrates.dailymed.api.label_events", new_callable=AsyncMock)
@patch("hypokrates.scan.api.cross_api.hypothesis")
@patch("hypokrates.scan.api.faers_api.top_events")
async def test_scan_passes_check_labels_and_trials(
    mock_top_events: AsyncMock,
    mock_hypothesis: AsyncMock,
    mock_label_events: AsyncMock,
) -> None:
    """check_labels/check_trials são passados para hypothesis()."""
    from hypokrates.dailymed.models import LabelEventsResult
    from hypokrates.models import MetaInfo as _Meta

    mock_top_events.return_value = make_events(["A"])
    mock_label_events.return_value = LabelEventsResult(
        drug="propofol", meta=_Meta(source="test", retrieved_at=datetime.now(UTC))
    )

    mock_hypothesis.return_value = _make_hypothesis_result(
        "A", HypothesisClassification.NOVEL_HYPOTHESIS
    )

    await scan_drug("propofol", top_n=1, check_labels=True, check_trials=True)

    mock_hypothesis.assert_called_once()
    call_kwargs = mock_hypothesis.call_args.kwargs
    assert call_kwargs["check_label"] is True
    assert call_kwargs["check_trials"] is True
    assert call_kwargs["_label_cache"] is not None


@patch("hypokrates.scan.api.cross_api.hypothesis")
@patch("hypokrates.scan.api.faers_api.top_events")
async def test_scan_items_have_label_fields(
    mock_top_events: AsyncMock,
    mock_hypothesis: AsyncMock,
) -> None:
    """ScanItem tem in_label e active_trials."""
    mock_top_events.return_value = make_events(["A"])

    mock_hypothesis.return_value = _make_hypothesis_result(
        "A",
        HypothesisClassification.NOVEL_HYPOTHESIS,
        in_label=False,
        active_trials=3,
    )

    result = await scan_drug("propofol", top_n=1)

    assert result.items[0].in_label is False
    assert result.items[0].active_trials == 3


class TestScore:
    """Testes para _score()."""

    def test_no_signal_score_zero(self) -> None:
        hyp = _make_hypothesis_result(
            "A", HypothesisClassification.NO_SIGNAL, signal_detected=False
        )
        assert _score(hyp) == 0.0

    def test_novel_higher_than_emerging(self) -> None:
        novel = _make_hypothesis_result(
            "A", HypothesisClassification.NOVEL_HYPOTHESIS, prr_lci=1.5, ror_lci=1.5
        )
        emerging = _make_hypothesis_result(
            "B",
            HypothesisClassification.EMERGING_SIGNAL,
            lit_count=3,
            prr_lci=1.5,
            ror_lci=1.5,
        )
        assert _score(novel) > _score(emerging)

    def test_negative_ci_clamped(self) -> None:
        hyp = _make_hypothesis_result(
            "A", HypothesisClassification.NOVEL_HYPOTHESIS, prr_lci=-0.5, ror_lci=-0.3
        )
        score = _score(hyp)
        # base * max(0.0, 0.1) = 10.0 * 0.1 = 1.0
        assert score == pytest.approx(1.0)

    def test_not_in_label_multiplier(self) -> None:
        """in_label=False -> score x LABEL_NOT_IN_MULTIPLIER."""
        base_hyp = _make_hypothesis_result(
            "A", HypothesisClassification.NOVEL_HYPOTHESIS, prr_lci=1.5, ror_lci=1.5
        )
        label_hyp = _make_hypothesis_result(
            "A",
            HypothesisClassification.NOVEL_HYPOTHESIS,
            prr_lci=1.5,
            ror_lci=1.5,
            in_label=False,
        )
        base_score = _score(base_hyp)
        label_score = _score(label_hyp)
        assert label_score == pytest.approx(base_score * LABEL_NOT_IN_MULTIPLIER)

    def test_in_label_multiplier(self) -> None:
        """in_label=True -> score x LABEL_IN_MULTIPLIER."""
        base_hyp = _make_hypothesis_result(
            "A", HypothesisClassification.NOVEL_HYPOTHESIS, prr_lci=1.5, ror_lci=1.5
        )
        label_hyp = _make_hypothesis_result(
            "A",
            HypothesisClassification.NOVEL_HYPOTHESIS,
            prr_lci=1.5,
            ror_lci=1.5,
            in_label=True,
        )
        base_score = _score(base_hyp)
        label_score = _score(label_hyp)
        assert label_score == pytest.approx(base_score * LABEL_IN_MULTIPLIER)

    def test_label_none_no_multiplier(self) -> None:
        """in_label=None → sem modificador."""
        hyp = _make_hypothesis_result(
            "A", HypothesisClassification.NOVEL_HYPOTHESIS, prr_lci=1.5, ror_lci=1.5
        )
        assert hyp.in_label is None
        score = _score(hyp)
        # 10.0 * 1.5 = 15.0
        assert score == pytest.approx(15.0)


# ---------------------------------------------------------------------------
# Sprint 6: group_events, check_drugbank, check_opentargets
# ---------------------------------------------------------------------------


@patch("hypokrates.scan.api.cross_api.hypothesis")
@patch("hypokrates.scan.api.faers_api.top_events")
async def test_scan_group_events_merges_synonyms(
    mock_top_events: AsyncMock,
    mock_hypothesis: AsyncMock,
) -> None:
    """group_events=True consolida sinônimos MedDRA."""
    mock_top_events.return_value = make_events(
        ["ANAPHYLACTIC SHOCK", "ANAPHYLACTIC REACTION", "BRADYCARDIA"]
    )

    mock_hypothesis.side_effect = [
        _make_hypothesis_result(
            "ANAPHYLACTIC SHOCK", HypothesisClassification.NOVEL_HYPOTHESIS, prr_lci=3.0
        ),
        _make_hypothesis_result(
            "ANAPHYLACTIC REACTION", HypothesisClassification.EMERGING_SIGNAL, lit_count=2
        ),
        _make_hypothesis_result(
            "BRADYCARDIA", HypothesisClassification.KNOWN_ASSOCIATION, lit_count=10
        ),
    ]

    result = await scan_drug("propofol", top_n=3, group_events=True)

    assert result.groups_applied is True
    assert len(result.items) == 2  # ANAPHYLAXIS (merged) + BRADYCARDIA
    events = [item.event for item in result.items]
    assert "ANAPHYLAXIS" in events
    assert "BRADYCARDIA" in events


@patch("hypokrates.scan.api.cross_api.hypothesis")
@patch("hypokrates.scan.api.faers_api.top_events")
async def test_scan_group_events_disabled(
    mock_top_events: AsyncMock,
    mock_hypothesis: AsyncMock,
) -> None:
    """group_events=False mantém todos separados."""
    mock_top_events.return_value = make_events(["ANAPHYLACTIC SHOCK", "ANAPHYLACTIC REACTION"])

    mock_hypothesis.side_effect = [
        _make_hypothesis_result("ANAPHYLACTIC SHOCK", HypothesisClassification.NOVEL_HYPOTHESIS),
        _make_hypothesis_result(
            "ANAPHYLACTIC REACTION", HypothesisClassification.EMERGING_SIGNAL, lit_count=2
        ),
    ]

    result = await scan_drug("propofol", top_n=2, group_events=False)

    assert result.groups_applied is False
    assert len(result.items) == 2


@patch("hypokrates.drugbank.api.drug_info", new_callable=AsyncMock)
@patch("hypokrates.scan.api.cross_api.hypothesis")
@patch("hypokrates.scan.api.faers_api.top_events")
async def test_scan_check_drugbank(
    mock_top_events: AsyncMock,
    mock_hypothesis: AsyncMock,
    mock_drug_info: AsyncMock,
) -> None:
    """check_drugbank → ScanResult tem mechanism, interactions_count, cyp_enzymes."""
    from hypokrates.drugbank.models import DrugBankInfo, DrugEnzyme, DrugInteraction

    mock_top_events.return_value = make_events(["A"])
    mock_hypothesis.return_value = _make_hypothesis_result(
        "A", HypothesisClassification.NOVEL_HYPOTHESIS
    )
    mock_drug_info.return_value = DrugBankInfo(
        drugbank_id="DB00818",
        name="Propofol",
        mechanism_of_action="GABA-A potentiator",
        enzymes=[DrugEnzyme(name="CYP2B6", gene_name="CYP2B6")],
        interactions=[
            DrugInteraction(partner_id="DB00813", partner_name="Fentanyl"),
        ],
    )

    result = await scan_drug("propofol", top_n=1, check_drugbank=True, group_events=False)

    assert result.mechanism == "GABA-A potentiator"
    assert result.interactions_count == 1
    assert "CYP2B6" in result.cyp_enzymes
    # Verifica que _drugbank_cache foi passado para hypothesis
    call_kwargs = mock_hypothesis.call_args.kwargs
    assert call_kwargs["_drugbank_cache"] is not None


@patch("hypokrates.opentargets.api.drug_adverse_events", new_callable=AsyncMock)
@patch("hypokrates.scan.api.cross_api.hypothesis")
@patch("hypokrates.scan.api.faers_api.top_events")
async def test_scan_check_opentargets(
    mock_top_events: AsyncMock,
    mock_hypothesis: AsyncMock,
    mock_ot_events: AsyncMock,
) -> None:
    """check_opentargets → _ot_safety_cache passado para hypothesis."""
    from hypokrates.opentargets.models import OTDrugSafety

    mock_top_events.return_value = make_events(["A"])
    mock_hypothesis.return_value = _make_hypothesis_result(
        "A", HypothesisClassification.NOVEL_HYPOTHESIS
    )
    mock_ot_events.return_value = OTDrugSafety(
        drug_name="propofol",
        chembl_id="CHEMBL526",
        meta=make_meta(),
    )

    result = await scan_drug("propofol", top_n=1, check_opentargets=True, group_events=False)

    call_kwargs = mock_hypothesis.call_args.kwargs
    assert call_kwargs["check_opentargets"] is True
    assert call_kwargs["_ot_safety_cache"] is not None
    assert result.total_scanned == 1


# ---------------------------------------------------------------------------
# Sprint 7: filter_operational, volume_flag
# ---------------------------------------------------------------------------


@patch("hypokrates.scan.api.cross_api.hypothesis")
@patch("hypokrates.scan.api.faers_api.top_events")
async def test_scan_filter_operational_removes_blocklisted_terms(
    mock_top_events: AsyncMock,
    mock_hypothesis: AsyncMock,
) -> None:
    """filter_operational=True remove termos operacionais antes de rodar hypothesis."""
    mock_top_events.return_value = make_events(
        ["NAUSEA", "OFF LABEL USE", "DRUG INEFFECTIVE", "DEATH", "HEADACHE"]
    )

    mock_hypothesis.side_effect = [
        _make_hypothesis_result("NAUSEA", HypothesisClassification.KNOWN_ASSOCIATION),
        _make_hypothesis_result("HEADACHE", HypothesisClassification.KNOWN_ASSOCIATION),
    ]

    result = await scan_drug("propofol", top_n=5, filter_operational=True)

    # hypothesis() chamado apenas 2x (NAUSEA + HEADACHE), operacionais filtrados
    assert mock_hypothesis.call_count == 2
    assert result.filtered_operational_count == 3
    assert result.total_scanned == 2
    events = [item.event for item in result.items]
    assert "OFF LABEL USE" not in events
    assert "DRUG INEFFECTIVE" not in events
    assert "DEATH" not in events


@patch("hypokrates.scan.api.cross_api.hypothesis")
@patch("hypokrates.scan.api.faers_api.top_events")
async def test_scan_filter_operational_disabled(
    mock_top_events: AsyncMock,
    mock_hypothesis: AsyncMock,
) -> None:
    """filter_operational=False mantém todos os termos."""
    mock_top_events.return_value = make_events(["NAUSEA", "OFF LABEL USE"])

    mock_hypothesis.side_effect = [
        _make_hypothesis_result("NAUSEA", HypothesisClassification.KNOWN_ASSOCIATION),
        _make_hypothesis_result("OFF LABEL USE", HypothesisClassification.KNOWN_ASSOCIATION),
    ]

    result = await scan_drug("propofol", top_n=2, filter_operational=False)

    assert mock_hypothesis.call_count == 2
    assert result.filtered_operational_count == 0
    events = [item.event for item in result.items]
    assert "OFF LABEL USE" in events


@patch("hypokrates.scan.api.cross_api.hypothesis")
@patch("hypokrates.scan.api.faers_api.top_events")
async def test_scan_volume_flag_set_when_above_threshold(
    mock_top_events: AsyncMock,
    mock_hypothesis: AsyncMock,
) -> None:
    """volume_flag=True quando cell a >= VOLUME_ANOMALY_THRESHOLD."""
    mock_top_events.return_value = make_events(["NAUSEA"])

    # Criar hypothesis com signal que tem a=5000 (acima do limiar de 2000)
    hyp = _make_hypothesis_result("NAUSEA", HypothesisClassification.KNOWN_ASSOCIATION)
    hyp.signal = SignalResult(
        drug="propofol",
        event="NAUSEA",
        table=ContingencyTable(a=5000, b=900, c=50, d=9000),
        prr=DisproportionalityResult(
            measure="PRR", value=2.0, ci_lower=1.5, ci_upper=3.0, significant=True
        ),
        ror=DisproportionalityResult(
            measure="ROR", value=2.1, ci_lower=1.6, ci_upper=3.1, significant=True
        ),
        ic=DisproportionalityResult(
            measure="IC", value=1.0, ci_lower=0.5, ci_upper=1.5, significant=True
        ),
        ebgm=DisproportionalityResult(
            measure="EBGM", value=2.0, ci_lower=1.5, ci_upper=2.5, significant=True
        ),
        signal_detected=True,
        meta=make_meta(),
    )
    mock_hypothesis.return_value = hyp

    result = await scan_drug("propofol", top_n=1, group_events=False)

    assert len(result.items) == 1
    assert result.items[0].volume_flag is True


@patch("hypokrates.scan.api.cross_api.hypothesis")
@patch("hypokrates.scan.api.faers_api.top_events")
async def test_scan_volume_flag_false_when_below_threshold(
    mock_top_events: AsyncMock,
    mock_hypothesis: AsyncMock,
) -> None:
    """volume_flag=False quando cell a < VOLUME_ANOMALY_THRESHOLD."""
    mock_top_events.return_value = make_events(["NAUSEA"])

    mock_hypothesis.return_value = _make_hypothesis_result(
        "NAUSEA", HypothesisClassification.KNOWN_ASSOCIATION
    )

    result = await scan_drug("propofol", top_n=1, group_events=False)

    assert len(result.items) == 1
    assert result.items[0].volume_flag is False


@patch("hypokrates.scan.api.cross_api.hypothesis")
@patch("hypokrates.scan.api.faers_api.top_events")
async def test_scan_filter_operational_case_insensitive(
    mock_top_events: AsyncMock,
    mock_hypothesis: AsyncMock,
) -> None:
    """Filtro operacional funciona independente de case."""
    mock_top_events.return_value = make_events(["off label use", "NAUSEA"])

    mock_hypothesis.return_value = _make_hypothesis_result(
        "NAUSEA", HypothesisClassification.KNOWN_ASSOCIATION
    )

    result = await scan_drug("propofol", top_n=2, filter_operational=True)

    assert mock_hypothesis.call_count == 1
    assert result.filtered_operational_count == 1


@patch("hypokrates.scan.api.cross_api.hypothesis")
@patch("hypokrates.scan.api.faers_api.top_events")
async def test_scan_suspect_only_propagated(
    mock_top_events: AsyncMock,
    mock_hypothesis: AsyncMock,
) -> None:
    """suspect_only propaga para top_events e hypothesis."""
    mock_top_events.return_value = make_events(["NAUSEA"])
    mock_hypothesis.return_value = _make_hypothesis_result(
        "NAUSEA", HypothesisClassification.KNOWN_ASSOCIATION
    )

    await scan_drug("propofol", top_n=1, suspect_only=True, group_events=False)

    # top_events chamado com suspect_only=True
    call_kwargs = mock_top_events.call_args.kwargs
    assert call_kwargs["suspect_only"] is True

    # hypothesis chamado com suspect_only=True
    hyp_kwargs = mock_hypothesis.call_args.kwargs
    assert hyp_kwargs["suspect_only"] is True


@patch("hypokrates.scan.api.cross_api.hypothesis")
@patch("hypokrates.scan.api.faers_api.top_events")
async def test_scan_overfetch_fetches_more_than_top_n(
    mock_top_events: AsyncMock,
    mock_hypothesis: AsyncMock,
) -> None:
    """Over-fetch busca top_n*3 eventos mas retorna top_n por score."""
    # Simular 9 eventos retornados (top_n=3, fetch_limit=9)
    mock_top_events.return_value = make_events(["A", "B", "C", "D", "E", "F", "G", "H", "I"])

    mock_hypothesis.side_effect = [
        _make_hypothesis_result("A", HypothesisClassification.KNOWN_ASSOCIATION, prr_lci=1.0),
        _make_hypothesis_result("B", HypothesisClassification.KNOWN_ASSOCIATION, prr_lci=0.5),
        _make_hypothesis_result("C", HypothesisClassification.KNOWN_ASSOCIATION, prr_lci=0.3),
        _make_hypothesis_result("D", HypothesisClassification.KNOWN_ASSOCIATION, prr_lci=0.2),
        _make_hypothesis_result("E", HypothesisClassification.KNOWN_ASSOCIATION, prr_lci=0.1),
        # F tem PRR alto — deve aparecer no top 3 apesar de volume baixo
        _make_hypothesis_result("F", HypothesisClassification.NOVEL_HYPOTHESIS, prr_lci=20.0),
        _make_hypothesis_result("G", HypothesisClassification.KNOWN_ASSOCIATION, prr_lci=0.1),
        _make_hypothesis_result("H", HypothesisClassification.KNOWN_ASSOCIATION, prr_lci=0.1),
        _make_hypothesis_result("I", HypothesisClassification.KNOWN_ASSOCIATION, prr_lci=0.1),
    ]

    result = await scan_drug("propofol", top_n=3, group_events=False)

    # top_events chamado com limit=9 (3*3)
    call_kwargs = mock_top_events.call_args.kwargs
    assert call_kwargs["limit"] == 9

    # hypothesis chamado 9x (todos os eventos)
    assert mock_hypothesis.call_count == 9

    # Resultado truncado para 3 items
    assert len(result.items) == 3

    # F (PRR alto, novel) deve estar no resultado apesar de ser #6 por volume
    events = [item.event for item in result.items]
    assert "F" in events

    # Ranks corretos (1-3)
    assert result.items[0].rank == 1
    assert result.items[2].rank == 3


# ---------------------------------------------------------------------------
# Sprint 8: check_chembl enrichment, progress on failure
# ---------------------------------------------------------------------------


@patch("hypokrates.chembl.api.drug_mechanism", new_callable=AsyncMock)
@patch("hypokrates.scan.api.cross_api.hypothesis")
@patch("hypokrates.scan.api.faers_api.top_events")
async def test_scan_check_chembl_enrichment(
    mock_top_events: AsyncMock,
    mock_hypothesis: AsyncMock,
    mock_chembl: AsyncMock,
) -> None:
    """check_chembl → ScanResult tem mechanism e cyp_enzymes do ChEMBL."""
    from hypokrates.chembl.models import ChEMBLMechanism, ChEMBLTarget

    mock_top_events.return_value = make_events(["A"])
    mock_hypothesis.return_value = _make_hypothesis_result(
        "A", HypothesisClassification.NOVEL_HYPOTHESIS
    )
    mock_chembl.return_value = ChEMBLMechanism(
        chembl_id="CHEMBL526",
        drug_name="Propofol",
        mechanism_of_action="GABA-A receptor positive allosteric modulator",
        targets=[
            ChEMBLTarget(
                target_chembl_id="CHEMBL2093872",
                name="GABA-A receptor",
                gene_names=["GABRA1", "GABRA2"],
            ),
        ],
        meta=make_meta(),
    )

    result = await scan_drug("propofol", top_n=1, check_chembl=True, group_events=False)

    assert result.mechanism == "GABA-A receptor positive allosteric modulator"
    assert "GABRA1" in result.cyp_enzymes
    assert "GABRA2" in result.cyp_enzymes
    # Verifica que _chembl_cache foi passado para hypothesis
    call_kwargs = mock_hypothesis.call_args.kwargs
    assert call_kwargs["check_chembl"] is True


@patch("hypokrates.scan.api.cross_api.hypothesis")
@patch("hypokrates.scan.api.faers_api.top_events")
async def test_scan_progress_on_failure(
    mock_top_events: AsyncMock,
    mock_hypothesis: AsyncMock,
) -> None:
    """on_progress é chamado mesmo quando hypothesis falha."""
    mock_top_events.return_value = make_events(["A", "B"])

    mock_hypothesis.side_effect = [
        RuntimeError("API error"),
        _make_hypothesis_result("B", HypothesisClassification.KNOWN_ASSOCIATION, lit_count=10),
    ]

    progress_calls: list[tuple[int, int, str]] = []

    def on_progress(completed: int, total: int, event: str) -> None:
        progress_calls.append((completed, total, event))

    await scan_drug("propofol", top_n=2, on_progress=on_progress)

    # Progress deve ter sido chamado para ambos (sucesso e falha)
    assert len(progress_calls) == 2


# ---------------------------------------------------------------------------
# Bulk top_events + direction analysis
# ---------------------------------------------------------------------------


@patch("hypokrates.scan.api._check_bulk_available", new_callable=AsyncMock)
@patch("hypokrates.faers_bulk.api.bulk_drug_total", new_callable=AsyncMock)
@patch("hypokrates.faers_bulk.api.bulk_top_events", new_callable=AsyncMock)
@patch("hypokrates.scan.api.cross_api.hypothesis")
async def test_scan_bulk_mode_uses_bulk_top_events(
    mock_hypothesis: AsyncMock,
    mock_bulk_top: AsyncMock,
    mock_bulk_total: AsyncMock,
    mock_bulk_avail: AsyncMock,
) -> None:
    """use_bulk=True usa bulk_top_events em vez de faers_api.top_events."""
    mock_bulk_avail.return_value = True
    mock_bulk_top.return_value = [("NAUSEA", 50), ("HEADACHE", 30)]
    mock_bulk_total.return_value = 100

    # Mock count_total (N total)
    with patch("hypokrates.faers_bulk.store.FAERSBulkStore.get_instance") as mock_store:
        mock_instance = mock_store.return_value
        mock_instance.count_total.return_value = 1000

        mock_hypothesis.side_effect = [
            _make_hypothesis_result("NAUSEA", HypothesisClassification.KNOWN_ASSOCIATION),
            _make_hypothesis_result(
                "HEADACHE", HypothesisClassification.EMERGING_SIGNAL, lit_count=3
            ),
        ]

        result = await scan_drug("propofol", top_n=2, use_bulk=True, group_events=False)

    assert result.bulk_mode is True
    assert result.role_filter_used == "all"
    mock_bulk_top.assert_called_once()


@patch("hypokrates.scan.api._check_bulk_available", new_callable=AsyncMock)
@patch("hypokrates.faers_bulk.api.bulk_drug_total", new_callable=AsyncMock)
@patch("hypokrates.faers_bulk.api.bulk_top_events", new_callable=AsyncMock)
@patch("hypokrates.scan.api.cross_api.hypothesis")
async def test_scan_primary_suspect_only_sets_ps_only(
    mock_hypothesis: AsyncMock,
    mock_bulk_top: AsyncMock,
    mock_bulk_total: AsyncMock,
    mock_bulk_avail: AsyncMock,
) -> None:
    """primary_suspect_only=True → role_filter_used='ps_only'."""
    mock_bulk_avail.return_value = True
    mock_bulk_top.return_value = [("NAUSEA", 50)]
    mock_bulk_total.return_value = 100

    with patch("hypokrates.faers_bulk.store.FAERSBulkStore.get_instance") as mock_store:
        mock_instance = mock_store.return_value
        mock_instance.count_total.return_value = 1000

        mock_hypothesis.return_value = _make_hypothesis_result(
            "NAUSEA", HypothesisClassification.KNOWN_ASSOCIATION
        )

        result = await scan_drug(
            "propofol", top_n=1, use_bulk=True, primary_suspect_only=True, group_events=False
        )

    assert result.role_filter_used == "ps_only"
    call_kwargs = mock_bulk_top.call_args.kwargs
    from hypokrates.faers_bulk.constants import RoleCodFilter

    assert call_kwargs["role_filter"] == RoleCodFilter.PS_ONLY


@patch("hypokrates.scan.api.cross_api.hypothesis")
@patch("hypokrates.scan.api.faers_api.top_events")
async def test_scan_primary_suspect_only_fallback_without_bulk(
    mock_top_events: AsyncMock,
    mock_hypothesis: AsyncMock,
) -> None:
    """primary_suspect_only=True sem bulk → warning, fallback to suspect_only."""
    mock_top_events.return_value = make_events(["NAUSEA"])
    mock_hypothesis.return_value = _make_hypothesis_result(
        "NAUSEA", HypothesisClassification.KNOWN_ASSOCIATION
    )

    result = await scan_drug(
        "propofol", top_n=1, use_bulk=False, primary_suspect_only=True, group_events=False
    )

    assert result.bulk_mode is False
    assert result.role_filter_used is None


@patch("hypokrates.faers_bulk.api.bulk_signal", new_callable=AsyncMock)
@patch("hypokrates.scan.api._check_bulk_available", new_callable=AsyncMock)
@patch("hypokrates.faers_bulk.api.bulk_drug_total", new_callable=AsyncMock)
@patch("hypokrates.faers_bulk.api.bulk_top_events", new_callable=AsyncMock)
@patch("hypokrates.scan.api.cross_api.hypothesis")
async def test_scan_direction_analysis_strengthens(
    mock_hypothesis: AsyncMock,
    mock_bulk_top: AsyncMock,
    mock_bulk_total: AsyncMock,
    mock_bulk_avail: AsyncMock,
    mock_bulk_signal: AsyncMock,
) -> None:
    """check_direction=True + PS PRR > 1.2x base → 'strengthens'."""
    mock_bulk_avail.return_value = True
    mock_bulk_top.return_value = [("NAUSEA", 50)]
    mock_bulk_total.return_value = 100

    with patch("hypokrates.faers_bulk.store.FAERSBulkStore.get_instance") as mock_store:
        mock_instance = mock_store.return_value
        mock_instance.count_total.return_value = 1000

        # Base hypothesis com PRR=2.0
        mock_hypothesis.return_value = _make_hypothesis_result(
            "NAUSEA", HypothesisClassification.EMERGING_SIGNAL, lit_count=3, prr_lci=1.5
        )

        # PS-only signal com PRR=3.0 (> 2.0 * 1.2 = 2.4 → strengthens)
        mock_bulk_signal.return_value = make_signal(prr_lci=2.5)
        mock_bulk_signal.return_value = SignalResult(
            drug="propofol",
            event="NAUSEA",
            table=ContingencyTable(a=100, b=900, c=50, d=9000),
            prr=DisproportionalityResult(
                measure="PRR", value=3.0, ci_lower=2.5, ci_upper=4.0, significant=True
            ),
            ror=DisproportionalityResult(
                measure="ROR", value=3.1, ci_lower=2.5, ci_upper=4.0, significant=True
            ),
            ic=DisproportionalityResult(
                measure="IC", value=1.0, ci_lower=0.5, ci_upper=1.5, significant=True
            ),
            ebgm=DisproportionalityResult(
                measure="EBGM", value=3.0, ci_lower=2.5, ci_upper=3.5, significant=True
            ),
            signal_detected=True,
            meta=make_meta(),
        )

        result = await scan_drug(
            "propofol", top_n=1, use_bulk=True, check_direction=True, group_events=False
        )

    assert len(result.items) == 1
    item = result.items[0]
    assert item.ps_only_prr == pytest.approx(3.0)
    assert item.direction == "strengthens"


@patch("hypokrates.faers_bulk.api.bulk_signal", new_callable=AsyncMock)
@patch("hypokrates.scan.api._check_bulk_available", new_callable=AsyncMock)
@patch("hypokrates.faers_bulk.api.bulk_drug_total", new_callable=AsyncMock)
@patch("hypokrates.faers_bulk.api.bulk_top_events", new_callable=AsyncMock)
@patch("hypokrates.scan.api.cross_api.hypothesis")
async def test_scan_direction_analysis_weakens(
    mock_hypothesis: AsyncMock,
    mock_bulk_top: AsyncMock,
    mock_bulk_total: AsyncMock,
    mock_bulk_avail: AsyncMock,
    mock_bulk_signal: AsyncMock,
) -> None:
    """check_direction=True + PS PRR < 0.8x base → 'weakens'."""
    mock_bulk_avail.return_value = True
    mock_bulk_top.return_value = [("NAUSEA", 50)]
    mock_bulk_total.return_value = 100

    with patch("hypokrates.faers_bulk.store.FAERSBulkStore.get_instance") as mock_store:
        mock_instance = mock_store.return_value
        mock_instance.count_total.return_value = 1000

        # Base hypothesis com PRR=2.0
        mock_hypothesis.return_value = _make_hypothesis_result(
            "NAUSEA", HypothesisClassification.EMERGING_SIGNAL, lit_count=3, prr_lci=1.5
        )

        # PS-only signal com PRR=1.0 (< 2.0 * 0.8 = 1.6 → weakens)
        mock_bulk_signal.return_value = SignalResult(
            drug="propofol",
            event="NAUSEA",
            table=ContingencyTable(a=100, b=900, c=50, d=9000),
            prr=DisproportionalityResult(
                measure="PRR", value=1.0, ci_lower=0.5, ci_upper=1.5, significant=False
            ),
            ror=DisproportionalityResult(
                measure="ROR", value=1.0, ci_lower=0.5, ci_upper=1.5, significant=False
            ),
            ic=DisproportionalityResult(
                measure="IC", value=0.5, ci_lower=0.1, ci_upper=0.9, significant=False
            ),
            ebgm=DisproportionalityResult(
                measure="EBGM", value=1.0, ci_lower=0.5, ci_upper=1.5, significant=False
            ),
            signal_detected=True,
            meta=make_meta(),
        )

        result = await scan_drug(
            "propofol", top_n=1, use_bulk=True, check_direction=True, group_events=False
        )

    assert len(result.items) == 1
    item = result.items[0]
    assert item.ps_only_prr == pytest.approx(1.0)
    assert item.direction == "weakens"


@patch("hypokrates.scan.api.cross_api.hypothesis")
@patch("hypokrates.scan.api.faers_api.top_events")
async def test_scan_direction_skipped_without_bulk(
    mock_top_events: AsyncMock,
    mock_hypothesis: AsyncMock,
) -> None:
    """check_direction=True sem bulk → ignorado (sem PS-only sem bulk)."""
    mock_top_events.return_value = make_events(["NAUSEA"])
    mock_hypothesis.return_value = _make_hypothesis_result(
        "NAUSEA", HypothesisClassification.EMERGING_SIGNAL, lit_count=3
    )

    result = await scan_drug(
        "propofol", top_n=1, use_bulk=False, check_direction=True, group_events=False
    )

    assert result.items[0].ps_only_prr is None
    assert result.items[0].direction is None
