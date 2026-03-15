"""Testes para faers_bulk/parser.py — parser de FAERS ASCII ZIPs."""

from __future__ import annotations

from pathlib import Path

import pytest

from hypokrates.faers_bulk.parser import parse_quarter_zip

GOLDEN_ZIP = Path(__file__).parent.parent / "golden_data" / "faers_bulk" / "faers_ascii_2024Q3.zip"


class TestParseQuarterZip:
    """Testes do parser de ZIP completo."""

    def test_parse_returns_three_lists(self) -> None:
        demo, drug, reac = parse_quarter_zip(GOLDEN_ZIP)
        assert isinstance(demo, list)
        assert isinstance(drug, list)
        assert isinstance(reac, list)

    def test_demo_count(self) -> None:
        """DEMO deve ter 9 rows (8 reports + header)."""
        demo, _, _ = parse_quarter_zip(GOLDEN_ZIP)
        assert len(demo) == 9

    def test_drug_count(self) -> None:
        """DRUG deve ter 12 rows."""
        _, drug, _ = parse_quarter_zip(GOLDEN_ZIP)
        assert len(drug) == 12

    def test_reac_count(self) -> None:
        """REAC deve ter 11 rows."""
        _, _, reac = parse_quarter_zip(GOLDEN_ZIP)
        assert len(reac) == 11

    def test_demo_keys(self) -> None:
        """Demo rows devem ter chaves esperadas em lowercase."""
        demo, _, _ = parse_quarter_zip(GOLDEN_ZIP)
        row = demo[0]
        assert "primaryid" in row
        assert "caseid" in row
        assert "caseversion" in row

    def test_drug_has_norm(self) -> None:
        """Drug rows devem ter drug_name_norm calculado."""
        _, drug, _ = parse_quarter_zip(GOLDEN_ZIP)
        # Primeiro drug row tem prod_ai=PROPOFOL
        propofol_rows = [r for r in drug if r.get("drug_name_norm") == "PROPOFOL"]
        assert len(propofol_rows) > 0

    def test_reac_has_pt_upper(self) -> None:
        """Reac rows devem ter pt_upper calculado."""
        _, _, reac = parse_quarter_zip(GOLDEN_ZIP)
        brady_rows = [r for r in reac if r.get("pt_upper") == "BRADYCARDIA"]
        assert len(brady_rows) > 0

    def test_missing_file_raises(self, tmp_path: Path) -> None:
        """ZIP sem arquivo DEMO deve levantar ValueError."""
        import zipfile

        bad_zip = tmp_path / "bad.zip"
        with zipfile.ZipFile(bad_zip, "w") as zf:
            zf.writestr("OTHER.txt", "data")

        with pytest.raises(ValueError, match="DEMO"):
            parse_quarter_zip(bad_zip)

    def test_nonexistent_zip_raises(self) -> None:
        """ZIP inexistente deve levantar FileNotFoundError."""
        with pytest.raises(FileNotFoundError):
            parse_quarter_zip("/nonexistent/path.zip")
