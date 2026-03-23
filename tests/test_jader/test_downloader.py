"""Tests for hypokrates.jader.downloader — JADER download helper."""

from __future__ import annotations


class TestJaderInstructions:
    """Tests for JADER manual download instructions."""

    def test_instructions_contain_url(self) -> None:
        from hypokrates.jader.downloader import JADER_INSTRUCTIONS

        assert "pmda.go.jp" in JADER_INSTRUCTIONS

    def test_instructions_contain_steps(self) -> None:
        from hypokrates.jader.downloader import JADER_INSTRUCTIONS

        assert "CAPTCHA" in JADER_INSTRUCTIONS
        assert "configure" in JADER_INSTRUCTIONS
        assert "jader_bulk_path" in JADER_INSTRUCTIONS
