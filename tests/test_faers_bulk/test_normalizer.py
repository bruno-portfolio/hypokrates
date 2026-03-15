"""Testes para faers_bulk/normalizer.py — normalização de nomes de droga."""

from __future__ import annotations

import pytest

from hypokrates.faers_bulk.normalizer import normalize_drug_name


class TestNormalizeDrugName:
    """Testes de normalização de nomes de droga."""

    def test_prod_ai_has_priority(self) -> None:
        """prod_ai deve ter prioridade sobre drugname."""
        result = normalize_drug_name("PROPOFOL", "DIPRIVAN 10MG/ML")
        assert result == "PROPOFOL"

    def test_drugname_fallback(self) -> None:
        """Se prod_ai vazio, usa drugname."""
        result = normalize_drug_name("", "FENTANYL CITRATE")
        assert result == "FENTANYL CITRATE"

    def test_drugname_dose_removal(self) -> None:
        """Remove informação de dose do drugname."""
        result = normalize_drug_name("", "PROPOFOL 10MG/ML")
        assert result == "PROPOFOL"

    def test_drugname_dose_mcg(self) -> None:
        """Remove dose em MCG."""
        result = normalize_drug_name("", "FENTANYL 50MCG")
        assert result == "FENTANYL"

    def test_upper_case(self) -> None:
        """Resultado sempre em uppercase."""
        result = normalize_drug_name("propofol", "")
        assert result == "PROPOFOL"

    def test_empty_both(self) -> None:
        """Ambos vazios retorna string vazia."""
        result = normalize_drug_name("", "")
        assert result == ""

    def test_backslash_n(self) -> None:
        r"""Valor \\N (FAERS null marker) retorna vazio."""
        result = normalize_drug_name("\\N", "\\N")
        assert result == ""

    def test_trailing_punctuation(self) -> None:
        """Remove pontuação trailing."""
        result = normalize_drug_name("PROPOFOL.", "")
        assert result == "PROPOFOL"

    @pytest.mark.parametrize(
        ("prod_ai", "drugname", "expected"),
        [
            ("KETAMINE", "KETALAR", "KETAMINE"),
            ("", "MIDAZOLAM 5 MG", "MIDAZOLAM"),
            ("", "SEVOFLURANE 100%", "SEVOFLURANE"),
            ("DEXMEDETOMIDINE HYDROCHLORIDE", "", "DEXMEDETOMIDINE HYDROCHLORIDE"),
        ],
    )
    def test_various_drugs(self, prod_ai: str, drugname: str, expected: str) -> None:
        """Testa normalização para várias drogas comuns."""
        result = normalize_drug_name(prod_ai, drugname)
        assert result == expected
