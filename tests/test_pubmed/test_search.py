"""Testes para hypokrates.pubmed.search — construção de queries."""

from __future__ import annotations

from hypokrates.pubmed.search import build_search_term


class TestBuildSearchTerm:
    """build_search_term — texto livre e MeSH."""

    def test_free_text(self) -> None:
        result = build_search_term("propofol", "hepatotoxicity")
        assert result == "propofol AND hepatotoxicity"

    def test_mesh_qualifiers(self) -> None:
        result = build_search_term("propofol", "hepatotoxicity", use_mesh=True)
        assert result == '"propofol"[MeSH] AND "hepatotoxicity"[MeSH]'

    def test_preserves_case(self) -> None:
        """build_search_term não altera case — PubMed é case-insensitive."""
        result = build_search_term("Propofol", "BRADYCARDIA")
        assert "Propofol" in result
        assert "BRADYCARDIA" in result

    def test_multi_word_terms(self) -> None:
        result = build_search_term("propofol", "cardiac arrest")
        assert result == "propofol AND cardiac arrest"

    def test_mesh_multi_word(self) -> None:
        result = build_search_term("propofol", "cardiac arrest", use_mesh=True)
        assert result == '"propofol"[MeSH] AND "cardiac arrest"[MeSH]'
