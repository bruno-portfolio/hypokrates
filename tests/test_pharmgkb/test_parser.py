"""Testes para pharmgkb/parser.py."""

from __future__ import annotations

import json
from pathlib import Path

from hypokrates.pharmgkb.parser import parse_annotations, parse_chemical_id, parse_guidelines

GOLDEN_DIR = Path(__file__).parent.parent / "golden_data" / "pharmgkb"


def _load(name: str) -> dict:
    return json.loads((GOLDEN_DIR / name).read_text())


class TestPharmGKBParser:
    """Testes do parser."""

    def test_parse_chemical_id(self) -> None:
        data = _load("chemical_propofol.json")
        result = parse_chemical_id(data)
        assert result == "PA450688"

    def test_parse_chemical_id_empty(self) -> None:
        result = parse_chemical_id({"data": []})
        assert result is None

    def test_parse_annotations_propofol(self) -> None:
        data = _load("annotations_propofol.json")
        anns = parse_annotations(data)
        assert len(anns) == 3
        assert anns[0].gene_symbol == "CYP2B6"
        assert anns[0].level_of_evidence == "3"
        assert "Metabolism/PK" in anns[0].annotation_types

    def test_parse_annotations_warfarin(self) -> None:
        data = _load("annotations_warfarin.json")
        anns = parse_annotations(data)
        assert len(anns) == 3
        vkorc1 = [a for a in anns if a.gene_symbol == "VKORC1"]
        assert len(vkorc1) == 1
        assert vkorc1[0].level_of_evidence == "1A"

    def test_parse_annotations_empty(self) -> None:
        anns = parse_annotations({"data": []})
        assert anns == []

    def test_parse_guidelines_warfarin(self) -> None:
        data = _load("guidelines_warfarin.json")
        guides = parse_guidelines(data)
        assert len(guides) == 2
        cpic = [g for g in guides if g.source == "CPIC"]
        assert len(cpic) == 1
        assert "VKORC1" in cpic[0].genes
        assert "CYP2C9" in cpic[0].genes
        assert cpic[0].recommendation is True

    def test_parse_guidelines_empty(self) -> None:
        guides = parse_guidelines({"data": []})
        assert guides == []
