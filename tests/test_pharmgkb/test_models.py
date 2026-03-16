"""Testes para pharmgkb/models.py."""

from __future__ import annotations

from datetime import UTC, datetime

from hypokrates.models import MetaInfo
from hypokrates.pharmgkb.models import (
    PharmGKBAnnotation,
    PharmGKBGuideline,
    PharmGKBResult,
)


class TestPharmGKBModels:
    """Testes dos modelos Pydantic."""

    def test_annotation(self) -> None:
        ann = PharmGKBAnnotation(
            accession_id="123",
            gene_symbol="CYP2B6",
            level_of_evidence="3",
            annotation_types=["Metabolism/PK"],
            score=1.5,
        )
        assert ann.gene_symbol == "CYP2B6"
        assert ann.level_of_evidence == "3"

    def test_annotation_defaults(self) -> None:
        ann = PharmGKBAnnotation()
        assert ann.gene_symbol == ""
        assert ann.annotation_types == []
        assert ann.score == 0.0

    def test_guideline(self) -> None:
        gl = PharmGKBGuideline(
            guideline_id="PA166104949",
            name="CPIC Warfarin",
            source="CPIC",
            genes=["VKORC1", "CYP2C9"],
            recommendation=True,
            summary="Dose adjustment based on genotype.",
        )
        assert gl.source == "CPIC"
        assert len(gl.genes) == 2
        assert gl.recommendation is True

    def test_result(self) -> None:
        result = PharmGKBResult(
            drug_name="propofol",
            pharmgkb_id="PA450688",
            annotations=[
                PharmGKBAnnotation(
                    gene_symbol="CYP2B6",
                    level_of_evidence="3",
                )
            ],
            meta=MetaInfo(
                source="PharmGKB",
                query={"drug": "propofol"},
                total_results=1,
                retrieved_at=datetime.now(UTC),
            ),
        )
        assert result.drug_name == "propofol"
        assert len(result.annotations) == 1
        assert result.guidelines == []

    def test_result_empty(self) -> None:
        result = PharmGKBResult(
            drug_name="unknown",
            meta=MetaInfo(
                source="PharmGKB",
                query={"drug": "unknown"},
                total_results=0,
                retrieved_at=datetime.now(UTC),
            ),
        )
        assert result.annotations == []
        assert result.guidelines == []
        assert result.pharmgkb_id is None
