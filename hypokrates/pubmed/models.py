"""Modelos PubMed — artigo e resultado de busca."""

from __future__ import annotations

from pydantic import BaseModel, Field

from hypokrates.models import MetaInfo  # noqa: TC001 — Pydantic needs at runtime


class PubMedArticle(BaseModel):
    """Artigo PubMed com metadados básicos."""

    pmid: str
    title: str
    authors: list[str] = Field(default_factory=list)
    journal: str | None = None
    pub_date: str | None = None
    doi: str | None = None


class PubMedSearchResult(BaseModel):
    """Resultado de uma busca no PubMed."""

    total_count: int = 0
    articles: list[PubMedArticle] = Field(default_factory=list)
    query_translation: str | None = None
    meta: MetaInfo
