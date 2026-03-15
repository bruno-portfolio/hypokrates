"""Testes para vocab/meddra.py — agrupamento MedDRA de termos sinônimos."""

from __future__ import annotations

import pytest

from hypokrates.vocab.meddra import (
    _ALIAS_MAP,
    MEDDRA_GROUPS,
    canonical_term,
    expand_event_terms,
    group_scan_items,
)

# ---------------------------------------------------------------------------
# expand_event_terms()
# ---------------------------------------------------------------------------


class TestExpandEventTerms:
    """Testes para expand_event_terms()."""

    def test_expand_canonical_term(self) -> None:
        terms = expand_event_terms("QT PROLONGATION")
        assert "QT PROLONGATION" in terms
        assert "ELECTROCARDIOGRAM QT PROLONGED" in terms
        assert "LONG QT SYNDROME" in terms
        assert "TORSADE DE POINTES" in terms
        assert len(terms) == 4

    def test_expand_alias_term(self) -> None:
        terms = expand_event_terms("ELECTROCARDIOGRAM QT PROLONGED")
        assert terms == ["ELECTROCARDIOGRAM QT PROLONGED"]

    def test_expand_unknown_term(self) -> None:
        terms = expand_event_terms("headache")
        assert terms == ["HEADACHE"]

    def test_expand_case_insensitive(self) -> None:
        terms = expand_event_terms("qt prolongation")
        assert "QT PROLONGATION" in terms
        assert len(terms) == 4

    def test_expand_with_whitespace(self) -> None:
        terms = expand_event_terms("  ANAPHYLAXIS  ")
        assert "ANAPHYLAXIS" in terms
        assert "ANAPHYLACTIC SHOCK" in terms
        assert len(terms) == 5

    def test_expand_empty_string(self) -> None:
        terms = expand_event_terms("")
        assert terms == [""]

    def test_expand_osteonecrosis(self) -> None:
        terms = expand_event_terms("OSTEONECROSIS")
        assert "OSTEONECROSIS" in terms
        assert "AVASCULAR NECROSIS" in terms
        assert "BONE NECROSIS" in terms
        assert "FEMORAL HEAD NECROSIS" in terms
        assert "OSTEONECROSIS OF JAW" in terms
        assert len(terms) == 5

    def test_expand_hyperglycaemia(self) -> None:
        terms = expand_event_terms("HYPERGLYCAEMIA")
        assert "HYPERGLYCAEMIA" in terms
        assert "BLOOD GLUCOSE INCREASED" in terms
        assert "DIABETES MELLITUS" in terms
        assert "HYPERGLYCEMIA" in terms
        assert "STEROID DIABETES" in terms
        assert "TYPE 2 DIABETES MELLITUS" in terms
        assert len(terms) == 6


# ---------------------------------------------------------------------------
# canonical_term()
# ---------------------------------------------------------------------------


class TestCanonicalTerm:
    """Testes para canonical_term()."""

    def test_alias_returns_canonical(self) -> None:
        assert canonical_term("ANAPHYLACTIC SHOCK") == "ANAPHYLAXIS"

    def test_alias_case_insensitive(self) -> None:
        assert canonical_term("anaphylactic shock") == "ANAPHYLAXIS"

    def test_alias_with_whitespace(self) -> None:
        assert canonical_term("  ANAPHYLACTIC SHOCK  ") == "ANAPHYLAXIS"

    def test_canonical_returns_itself(self) -> None:
        assert canonical_term("ANAPHYLAXIS") == "ANAPHYLAXIS"

    def test_canonical_case_insensitive(self) -> None:
        assert canonical_term("anaphylaxis") == "ANAPHYLAXIS"

    def test_unknown_term_returns_uppercased(self) -> None:
        assert canonical_term("some unknown term") == "SOME UNKNOWN TERM"

    def test_empty_string(self) -> None:
        assert canonical_term("") == ""

    def test_bradycardia_aliases(self) -> None:
        assert canonical_term("SINUS BRADYCARDIA") == "BRADYCARDIA"
        assert canonical_term("HEART RATE DECREASED") == "BRADYCARDIA"

    def test_respiratory_depression_aliases(self) -> None:
        assert canonical_term("APNOEA") == "RESPIRATORY DEPRESSION"
        assert canonical_term("APNEA") == "RESPIRATORY DEPRESSION"
        assert canonical_term("RESPIRATORY FAILURE") == "RESPIRATORY DEPRESSION"

    def test_hypotension_aliases(self) -> None:
        assert canonical_term("BLOOD PRESSURE DECREASED") == "HYPOTENSION"
        assert canonical_term("CIRCULATORY COLLAPSE") == "HYPOTENSION"

    def test_nausea_and_vomiting(self) -> None:
        assert canonical_term("VOMITING") == "NAUSEA AND VOMITING"
        assert canonical_term("RETCHING") == "NAUSEA AND VOMITING"

    def test_propofol_infusion_syndrome(self) -> None:
        assert canonical_term("PRIS") == "PROPOFOL INFUSION SYNDROME"

    def test_methemoglobinaemia_spellings(self) -> None:
        assert canonical_term("METHEMOGLOBINEMIA") == "METHEMOGLOBINAEMIA"
        assert canonical_term("METHAEMOGLOBINAEMIA") == "METHEMOGLOBINAEMIA"

    def test_canonical_avascular_necrosis(self) -> None:
        assert canonical_term("AVASCULAR NECROSIS") == "OSTEONECROSIS"

    def test_canonical_hyperglycemia(self) -> None:
        assert canonical_term("HYPERGLYCEMIA") == "HYPERGLYCAEMIA"
        assert canonical_term("BLOOD GLUCOSE INCREASED") == "HYPERGLYCAEMIA"
        assert canonical_term("STEROID DIABETES") == "HYPERGLYCAEMIA"

    def test_canonical_mood_disorder(self) -> None:
        assert canonical_term("MOOD SWINGS") == "MOOD DISORDER"
        assert canonical_term("AFFECT LABILITY") == "MOOD DISORDER"

    def test_canonical_psychiatric_disorder(self) -> None:
        assert canonical_term("PSYCHOSIS") == "PSYCHIATRIC DISORDER"
        assert canonical_term("STEROID PSYCHOSIS") == "PSYCHIATRIC DISORDER"

    def test_canonical_dvt(self) -> None:
        assert canonical_term("DVT") == "DEEP VEIN THROMBOSIS"
        assert canonical_term("VENOUS THROMBOSIS") == "DEEP VEIN THROMBOSIS"


# ---------------------------------------------------------------------------
# MEDDRA_GROUPS integrity
# ---------------------------------------------------------------------------


class TestMeddraGroupsIntegrity:
    """Testes de integridade do dicionário MEDDRA_GROUPS."""

    def test_all_canonical_terms_are_uppercase(self) -> None:
        for canonical in MEDDRA_GROUPS:
            assert canonical == canonical.upper(), f"Canonical not uppercase: {canonical}"

    def test_all_aliases_are_uppercase(self) -> None:
        for canonical, aliases in MEDDRA_GROUPS.items():
            for alias in aliases:
                assert alias == alias.upper(), f"Alias not uppercase: {alias} (group {canonical})"

    def test_no_duplicate_aliases(self) -> None:
        all_aliases: list[str] = []
        for aliases in MEDDRA_GROUPS.values():
            all_aliases.extend(aliases)
        assert len(all_aliases) == len(set(all_aliases)), "Duplicate aliases found"

    def test_no_alias_is_also_canonical(self) -> None:
        canonicals = set(MEDDRA_GROUPS.keys())
        for aliases in MEDDRA_GROUPS.values():
            for alias in aliases:
                assert alias not in canonicals, f"Alias {alias} is also a canonical term"

    def test_alias_map_matches_groups(self) -> None:
        count = sum(len(aliases) for aliases in MEDDRA_GROUPS.values())
        assert len(_ALIAS_MAP) == count

    def test_minimum_groups(self) -> None:
        assert len(MEDDRA_GROUPS) >= 30, f"Expected >=30 groups, got {len(MEDDRA_GROUPS)}"


# ---------------------------------------------------------------------------
# group_scan_items()
# ---------------------------------------------------------------------------


class TestGroupScanItems:
    """Testes para group_scan_items()."""

    @pytest.fixture()
    def _make_scan_item(self) -> object:
        """Factory para criar ScanItem mínimo."""
        from datetime import UTC, datetime

        from hypokrates.cross.models import HypothesisClassification
        from hypokrates.evidence.models import EvidenceBlock, Limitation
        from hypokrates.models import MetaInfo
        from hypokrates.scan.models import ScanItem
        from hypokrates.stats.models import (
            ContingencyTable,
            DisproportionalityResult,
            SignalResult,
        )

        def _make(
            event: str,
            score: float = 1.0,
            lit_count: int = 0,
            pmids: list[str] | None = None,
        ) -> ScanItem:
            table = ContingencyTable(a=10, b=100, c=50, d=10000)
            measure = DisproportionalityResult(
                measure="PRR", value=2.0, ci_lower=1.5, ci_upper=3.0, significant=True
            )
            signal = SignalResult(
                drug="test",
                event=event,
                signal_detected=True,
                table=table,
                prr=measure,
                ror=measure,
                ic=measure,
                meta=MetaInfo(
                    source="test",
                    retrieved_at=datetime.now(UTC),
                ),
            )
            evidence = EvidenceBlock(
                source="test",
                retrieved_at=datetime.now(UTC),
                methodology="test",
                limitations=[Limitation.NO_CAUSATION],
                confidence="test",
            )

            articles = []
            if pmids:
                from hypokrates.pubmed.models import PubMedArticle

                for pmid in pmids:
                    articles.append(PubMedArticle(pmid=pmid, title=f"Article {pmid}"))

            return ScanItem(
                drug="test",
                event=event,
                classification=HypothesisClassification.EMERGING_SIGNAL,
                signal=signal,
                literature_count=lit_count,
                articles=articles,
                evidence=evidence,
                summary=f"Test {event}",
                score=score,
                rank=1,
            )

        return _make

    def test_no_grouping_when_no_synonyms(self, _make_scan_item: object) -> None:
        make = _make_scan_item  # type: ignore[assignment]
        items = [make(event="DEATH"), make(event="PAIN")]
        result = group_scan_items(items)
        assert len(result) == 2
        assert result[0].grouped_terms == []
        assert result[1].grouped_terms == []

    def test_groups_synonyms(self, _make_scan_item: object) -> None:
        make = _make_scan_item  # type: ignore[assignment]
        items = [
            make(event="ANAPHYLACTIC SHOCK", score=5.0),
            make(event="ANAPHYLACTIC REACTION", score=3.0),
            make(event="ANAPHYLAXIS", score=4.0),
        ]
        result = group_scan_items(items)
        assert len(result) == 1
        assert result[0].event == "ANAPHYLAXIS"
        assert len(result[0].grouped_terms) == 3

    def test_highest_score_wins(self, _make_scan_item: object) -> None:
        make = _make_scan_item  # type: ignore[assignment]
        items = [
            make(event="SINUS BRADYCARDIA", score=10.0),
            make(event="HEART RATE DECREASED", score=2.0),
        ]
        result = group_scan_items(items)
        assert len(result) == 1
        assert result[0].event == "BRADYCARDIA"
        assert result[0].score == 10.0

    def test_merge_articles_dedup_by_pmid(self, _make_scan_item: object) -> None:
        make = _make_scan_item  # type: ignore[assignment]
        items = [
            make(event="ANAPHYLACTIC SHOCK", pmids=["1111", "2222"]),
            make(event="ANAPHYLAXIS", pmids=["2222", "3333"]),
        ]
        result = group_scan_items(items)
        assert len(result) == 1
        pmids = {art.pmid for art in result[0].articles}
        assert pmids == {"1111", "2222", "3333"}

    def test_sums_literature_count(self, _make_scan_item: object) -> None:
        make = _make_scan_item  # type: ignore[assignment]
        items = [
            make(event="VOMITING", lit_count=5),
            make(event="RETCHING", lit_count=3),
        ]
        result = group_scan_items(items)
        assert len(result) == 1
        assert result[0].literature_count == 8

    def test_re_ranks_after_grouping(self, _make_scan_item: object) -> None:
        make = _make_scan_item  # type: ignore[assignment]
        items = [
            make(event="DEATH", score=20.0),
            make(event="VOMITING", score=3.0),
            make(event="RETCHING", score=2.0),
        ]
        result = group_scan_items(items)
        assert len(result) == 2
        assert result[0].rank == 1
        assert result[1].rank == 2

    def test_single_alias_renamed(self, _make_scan_item: object) -> None:
        make = _make_scan_item  # type: ignore[assignment]
        items = [make(event="PLATELET COUNT DECREASED")]
        result = group_scan_items(items)
        assert len(result) == 1
        assert result[0].event == "THROMBOCYTOPENIA"
        assert result[0].grouped_terms == ["PLATELET COUNT DECREASED"]

    def test_empty_list(self) -> None:
        result = group_scan_items([])
        assert result == []
