"""Testes para hypokrates.utils.validation — nomes de medicamentos.

Validação de entrada é a primeira linha de defesa contra dados ruins.
Nomes de medicamentos válidos incluem caracteres ASCII, hifens, e pontos.
A regex atual não aceita unicode — se isso for necessário no futuro,
o teste documenta o comportamento atual.
"""

from __future__ import annotations

import pytest

from hypokrates.exceptions import ValidationError
from hypokrates.utils.validation import validate_drug_name


class TestDrugNameValidation:
    """Validação de nomes de medicamentos."""

    # ---- Nomes válidos ----

    @pytest.mark.parametrize(
        "name",
        [
            "propofol",
            "dexmedetomidine",
            "co-trimoxazole",
            "aspirin 100mg",
            "sodium chloride 0.9",
            "fentanyl",
            "N-acetylcysteine",
            "vitamin B12",
        ],
    )
    def test_valid_names_accepted(self, name: str) -> None:
        result = validate_drug_name(name)
        assert result == name

    # ---- Nomes inválidos ----

    def test_empty_rejected(self) -> None:
        with pytest.raises(ValidationError, match="empty"):
            validate_drug_name("")

    def test_whitespace_only_rejected(self) -> None:
        with pytest.raises(ValidationError, match="empty"):
            validate_drug_name("   ")

    def test_too_long_rejected(self) -> None:
        """201 chars → rejeitado."""
        long_name = "a" * 201
        with pytest.raises(ValidationError, match="too long"):
            validate_drug_name(long_name)

    def test_boundary_200_chars_accepted(self) -> None:
        """200 chars exato → aceito."""
        name = "a" * 200
        result = validate_drug_name(name)
        assert result == name

    def test_starts_with_digit_rejected(self) -> None:
        """'123drug' → rejeitado (regex exige letra no início)."""
        with pytest.raises(ValidationError, match="Invalid drug name"):
            validate_drug_name("123drug")

    def test_single_char_rejected(self) -> None:
        """Um caractere só não é suficiente para a regex (precisa de 2+)."""
        with pytest.raises(ValidationError, match="Invalid drug name"):
            validate_drug_name("a")

    def test_control_chars_rejected(self) -> None:
        """Null byte e control chars rejeitados."""
        with pytest.raises(ValidationError, match="Invalid drug name"):
            validate_drug_name("propofol\x00")

    def test_sql_injection_rejected(self) -> None:
        """SQL injection rejeitada."""
        with pytest.raises(ValidationError, match="Invalid drug name"):
            validate_drug_name('propofol"; DROP TABLE')

    def test_special_chars_rejected(self) -> None:
        """Caracteres especiais rejeitados."""
        with pytest.raises(ValidationError, match="Invalid drug name"):
            validate_drug_name("propofol@home")

    def test_newline_rejected(self) -> None:
        with pytest.raises(ValidationError, match="Invalid drug name"):
            validate_drug_name("propofol\ninjection")

    # ---- Unicode — comportamento atual documentado ----

    @pytest.mark.parametrize(
        "name",
        [
            "propoföl",  # umlaut
            "café-ergot",  # acento
            "naïve-compound",  # trema
            "日本語薬",  # CJK
        ],
    )
    def test_unicode_names_rejected_by_current_regex(self, name: str) -> None:
        """A regex atual é ASCII-only. Unicode é rejeitado.

        Se FAERS reports internacionais precisarem de unicode no futuro,
        esta decisão precisa ser consciente (atualizar regex + testes).
        """
        with pytest.raises(ValidationError, match="Invalid drug name"):
            validate_drug_name(name)

    # ---- Normalização ----

    def test_strips_leading_whitespace(self) -> None:
        result = validate_drug_name("  propofol")
        assert result == "propofol"

    def test_strips_trailing_whitespace(self) -> None:
        result = validate_drug_name("propofol  ")
        assert result == "propofol"

    def test_strips_both_whitespace(self) -> None:
        result = validate_drug_name("  propofol  ")
        assert result == "propofol"

    # ---- Formatos aceitos do domínio médico ----

    def test_hyphenated_drug_accepted(self) -> None:
        """Hifens são comuns em nomes compostos."""
        assert validate_drug_name("co-trimoxazole") == "co-trimoxazole"

    def test_dotted_drug_accepted(self) -> None:
        """Pontos são comuns em dosagens."""
        assert validate_drug_name("sodium chloride 0.9") == "sodium chloride 0.9"

    def test_drug_with_numbers_accepted(self) -> None:
        """Números no meio são comuns (B12, 5-HT3, etc.)."""
        assert validate_drug_name("vitamin B12") == "vitamin B12"
