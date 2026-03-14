"""Testes para hypokrates.utils.result — builders de metadados."""

from __future__ import annotations

from hypokrates.utils.result import build_source_meta, finalize_result


class TestBuildSourceMeta:
    """build_source_meta cria MetaInfo padronizado."""

    def test_creates_meta_with_defaults(self) -> None:
        meta = build_source_meta("OpenFDA/FAERS", {"drug": "propofol"})
        assert meta.source == "OpenFDA/FAERS"
        assert meta.query == {"drug": "propofol"}
        assert meta.total_results == 0
        assert meta.cached is False
        assert meta.retrieved_at is not None

    def test_creates_meta_with_total(self) -> None:
        meta = build_source_meta("PubMed", {"term": "aspirin"}, total=42)
        assert meta.total_results == 42

    def test_creates_meta_with_cached_flag(self) -> None:
        meta = build_source_meta("RxNorm", {}, cached=True)
        assert meta.cached is True


class TestFinalizeResult:
    """finalize_result atualiza flags de cache."""

    def test_marks_cached(self) -> None:
        meta = build_source_meta("FAERS", {})
        assert meta.cached is False
        result = finalize_result(meta, cached=True)
        assert result.cached is True
        assert result is meta  # mutação in-place

    def test_marks_not_cached(self) -> None:
        meta = build_source_meta("FAERS", {}, cached=True)
        result = finalize_result(meta, cached=False)
        assert result.cached is False
