"""Testes do parser ANVISA."""

from __future__ import annotations

from pathlib import Path

import pytest

from hypokrates.anvisa.parser import (
    normalize_text,
    parse_medicamentos_csv,
    split_apresentacoes,
    split_substancias,
)
from hypokrates.exceptions import ParseError

GOLDEN_CSV = Path(__file__).parent.parent / "golden_data" / "anvisa" / "sample_medicamentos.csv"


class TestNormalizeText:
    def test_uppercase(self) -> None:
        assert normalize_text("propofol") == "PROPOFOL"

    def test_strip_accents(self) -> None:
        assert normalize_text("ÁCIDO ACETILSALICÍLICO") == "ACIDO ACETILSALICILICO"

    def test_cedilha(self) -> None:
        assert normalize_text("AÇÚCAR") == "ACUCAR"

    def test_mixed(self) -> None:
        assert normalize_text("Cloridrato de Metformina") == "CLORIDRATO DE METFORMINA"

    def test_empty(self) -> None:
        assert normalize_text("") == ""

    def test_tilde(self) -> None:
        assert normalize_text("AÇÃO") == "ACAO"


class TestSplitSubstancias:
    def test_single(self) -> None:
        assert split_substancias("DIPIRONA") == ["DIPIRONA"]

    def test_comma_separated(self) -> None:
        result = split_substancias("DIPIRONA, CAFEÍNA")
        assert result == ["DIPIRONA", "CAFEÍNA"]

    def test_plus_separated(self) -> None:
        result = split_substancias("DIPIRONA + CAFEÍNA")
        assert result == ["DIPIRONA", "CAFEÍNA"]

    def test_empty(self) -> None:
        assert split_substancias("") == []

    def test_strip_whitespace(self) -> None:
        result = split_substancias("  PROPOFOL  ")
        assert result == ["PROPOFOL"]


class TestSplitApresentacoes:
    def test_multiple(self) -> None:
        result = split_apresentacoes("500mg comprimido, 1g comprimido")
        assert len(result) == 2
        assert result[0] == "500mg comprimido"

    def test_empty(self) -> None:
        assert split_apresentacoes("") == []

    def test_single(self) -> None:
        result = split_apresentacoes("10mg/ml injetável")
        assert result == ["10mg/ml injetável"]


class TestParseMedicamentosCSV:
    def test_parse_golden_data(self) -> None:
        rows = parse_medicamentos_csv(GOLDEN_CSV)
        assert len(rows) == 9

    def test_fields_present(self) -> None:
        rows = parse_medicamentos_csv(GOLDEN_CSV)
        row = rows[0]
        assert "registro" in row
        assert "nome_produto" in row
        assert "substancias" in row
        assert "substancias_norm" in row
        assert "categoria" in row
        assert "empresa" in row

    def test_novalgina_row(self) -> None:
        rows = parse_medicamentos_csv(GOLDEN_CSV)
        novalgina = next(r for r in rows if "NOVALGINA" in r["nome_produto"].upper())
        assert "dipirona" in novalgina["substancias"].lower()

    def test_substancias_norm(self) -> None:
        rows = parse_medicamentos_csv(GOLDEN_CSV)
        glifage = next(r for r in rows if "GLIFAGE" in r["nome_produto"].upper())
        assert "CLORIDRATO DE METFORMINA" in glifage["substancias_norm"]

    def test_registro_not_empty(self) -> None:
        rows = parse_medicamentos_csv(GOLDEN_CSV)
        for row in rows:
            assert row["registro"], f"Empty registro in row: {row['nome_produto']}"

    def test_invalid_csv_raises(self, tmp_path: Path) -> None:
        bad_csv = tmp_path / "bad.csv"
        bad_csv.write_text("COL_A;COL_B\na;b", encoding="latin-1")
        with pytest.raises(ParseError, match="Colunas obrigatorias faltando"):
            parse_medicamentos_csv(bad_csv)

    def test_empty_csv_raises(self, tmp_path: Path) -> None:
        empty_csv = tmp_path / "empty.csv"
        empty_csv.write_text("", encoding="latin-1")
        with pytest.raises(ParseError, match="CSV vazio"):
            parse_medicamentos_csv(empty_csv)
