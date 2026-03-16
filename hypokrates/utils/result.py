"""Helpers para construção de resultados."""

from __future__ import annotations

from datetime import UTC, datetime

from hypokrates.models import MetaInfo


def build_source_meta(
    source: str,
    query: dict[str, str | int | float | bool | None],
    total: int = 0,
    cached: bool = False,
) -> MetaInfo:
    """Cria MetaInfo padronizado."""
    return MetaInfo(
        source=source,
        query=query,
        total_results=total,
        cached=cached,
        retrieved_at=datetime.now(UTC),
    )


def finalize_result(meta: MetaInfo, *, cached: bool = False) -> MetaInfo:
    """Marca resultado como finalizado, atualizando flags."""
    meta.cached = cached
    return meta
