"""Testes para hypokrates.pubmed.classify — classificação de artigos."""

from __future__ import annotations

from hypokrates.pubmed.classify import classify_article
from tests.helpers import make_article


class TestClassifyArticle:
    def test_review(self) -> None:
        art = make_article(title="A systematic review of drug safety")
        assert classify_article(art) == "review"

    def test_meta_analysis(self) -> None:
        art = make_article(title="Meta-analysis of adverse reactions")
        assert classify_article(art) == "review"

    def test_case_report(self) -> None:
        art = make_article(title="We report a case of anaphylaxis")
        assert classify_article(art) == "case_report"

    def test_mechanism_via_abstract(self) -> None:
        art = make_article(title="Drug effects study")
        art.abstract = "We investigated the receptor pathway involved in this toxicity."
        assert classify_article(art) == "mechanism"

    def test_epidemiology(self) -> None:
        art = make_article(title="Retrospective cohort study of drug-induced liver injury")
        assert classify_article(art) == "epidemiology"

    def test_pharmacovigilance(self) -> None:
        art = make_article(title="Disproportionality analysis using FAERS data")
        assert classify_article(art) == "epidemiology"

    def test_clinical_trial(self) -> None:
        art = make_article(title="A randomized double-blind placebo-controlled trial")
        assert classify_article(art) == "clinical"

    def test_unclassified(self) -> None:
        art = make_article(title="General drug information update")
        assert classify_article(art) == ""

    def test_priority_review_over_mechanism(self) -> None:
        art = make_article(title="Systematic review of receptor mechanisms")
        assert classify_article(art) == "review"

    def test_case_insensitive(self) -> None:
        art = make_article(title="SYSTEMATIC REVIEW OF SAFETY")
        assert classify_article(art) == "review"
