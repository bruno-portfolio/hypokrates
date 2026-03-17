"""Testes para jader/mappings.py — tradução JP→EN."""

from __future__ import annotations

from hypokrates.jader.mappings import translate_drug, translate_event
from hypokrates.jader.models import MappingConfidence


class TestTranslateDrug:
    """Testes de tradução de nomes de drogas JP→EN."""

    def test_exact_match(self) -> None:
        name, conf = translate_drug("プロポフォール")
        assert name == "PROPOFOL"
        assert conf == MappingConfidence.EXACT

    def test_exact_match_ketamine(self) -> None:
        name, conf = translate_drug("ケタミン")
        assert name == "KETAMINE"
        assert conf == MappingConfidence.EXACT

    def test_ascii_romaji_inferred(self) -> None:
        name, conf = translate_drug("PROPOFOL")
        assert name == "PROPOFOL"
        assert conf == MappingConfidence.INFERRED

    def test_unmapped_japanese(self) -> None:
        _name, conf = translate_drug("未知薬品")
        assert conf == MappingConfidence.UNMAPPED

    def test_whitespace_stripped(self) -> None:
        name, conf = translate_drug("  プロポフォール  ")
        assert name == "PROPOFOL"
        assert conf == MappingConfidence.EXACT


class TestTranslateEvent:
    """Testes de tradução de termos MedDRA JP→EN."""

    def test_exact_match(self) -> None:
        name, conf = translate_event("徐脈")
        assert name == "BRADYCARDIA"
        assert conf == MappingConfidence.EXACT

    def test_exact_match_nausea(self) -> None:
        name, conf = translate_event("悪心")
        assert name == "NAUSEA"
        assert conf == MappingConfidence.EXACT

    def test_ascii_inferred(self) -> None:
        name, conf = translate_event("BRADYCARDIA")
        assert name == "BRADYCARDIA"
        assert conf == MappingConfidence.INFERRED

    def test_unmapped(self) -> None:
        _name, conf = translate_event("未知有害事象")
        assert conf == MappingConfidence.UNMAPPED

    def test_anaphylactic_shock(self) -> None:
        name, conf = translate_event("アナフィラキシーショック")
        assert name == "ANAPHYLACTIC SHOCK"
        assert conf == MappingConfidence.EXACT
