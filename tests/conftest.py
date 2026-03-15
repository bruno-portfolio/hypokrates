"""Fixtures compartilhadas para os testes."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from hypokrates.cache.duckdb_store import CacheStore
from hypokrates.config import reset_config
from hypokrates.drugbank.store import DrugBankStore
from hypokrates.http.rate_limiter import RateLimiter

GOLDEN_DATA = Path(__file__).parent / "golden_data"


@pytest.fixture(autouse=True)
def _reset_singletons() -> None:  # type: ignore[misc]
    """Reseta singletons entre testes."""
    reset_config()
    CacheStore.reset()
    RateLimiter.reset_all()
    DrugBankStore.reset()


# ---------------------------------------------------------------------------
# Golden data — adverse events, top events, no results (existentes)
# ---------------------------------------------------------------------------


@pytest.fixture()
def golden_faers_adverse_events() -> dict[str, Any]:
    """Fixture com golden data de adverse events do propofol."""
    path = GOLDEN_DATA / "faers" / "adverse_events_propofol.json"
    return json.loads(path.read_text())  # type: ignore[no-any-return]


@pytest.fixture()
def golden_faers_top_events() -> dict[str, Any]:
    """Fixture com golden data de top events do propofol."""
    path = GOLDEN_DATA / "faers" / "top_events_propofol.json"
    return json.loads(path.read_text())  # type: ignore[no-any-return]


@pytest.fixture()
def golden_faers_no_results() -> dict[str, Any]:
    """Fixture com golden data de busca sem resultados."""
    path = GOLDEN_DATA / "faers" / "no_results.json"
    return json.loads(path.read_text())  # type: ignore[no-any-return]


# ---------------------------------------------------------------------------
# Golden data — novos cenários de edge case
# ---------------------------------------------------------------------------


@pytest.fixture()
def golden_faers_malformed() -> dict[str, Any]:
    """Reports com campos faltando, tipos errados, dados incompletos."""
    path = GOLDEN_DATA / "faers" / "malformed_reports.json"
    return json.loads(path.read_text())  # type: ignore[no-any-return]


@pytest.fixture()
def golden_faers_demographics() -> dict[str, Any]:
    """Edge cases demográficos: idade 0, 120, None, 'abc'; sexo 0, 99, ausente."""
    path = GOLDEN_DATA / "faers" / "edge_case_demographics.json"
    return json.loads(path.read_text())  # type: ignore[no-any-return]


@pytest.fixture()
def golden_faers_multi_drug() -> dict[str, Any]:
    """Polifarmácia: 5+ drogas, roles mistos, fallback de nomes."""
    path = GOLDEN_DATA / "faers" / "multi_drug_complex.json"
    return json.loads(path.read_text())  # type: ignore[no-any-return]


@pytest.fixture()
def golden_faers_serious_all() -> dict[str, Any]:
    """Seriousness: todos os 6 flags, não sério, sério sem flags."""
    path = GOLDEN_DATA / "faers" / "serious_reasons_all.json"
    return json.loads(path.read_text())  # type: ignore[no-any-return]


@pytest.fixture()
def golden_faers_api_errors() -> dict[str, Any]:
    """Respostas de erro da API OpenFDA."""
    path = GOLDEN_DATA / "faers" / "api_error_responses.json"
    return json.loads(path.read_text())  # type: ignore[no-any-return]


@pytest.fixture()
def golden_faers_drugs_by_event() -> dict[str, Any]:
    """Golden data de drugs by event (reverse lookup: evento -> drogas)."""
    path = GOLDEN_DATA / "faers" / "drugs_by_event_anaphylaxis.json"
    return json.loads(path.read_text())  # type: ignore[no-any-return]


# ---------------------------------------------------------------------------
# Cache temporário
# ---------------------------------------------------------------------------


@pytest.fixture()
def tmp_cache(tmp_path: Path) -> CacheStore:
    """Cache DuckDB em diretório temporário."""
    db_path = tmp_path / "test_cache.duckdb"
    return CacheStore(db_path)
