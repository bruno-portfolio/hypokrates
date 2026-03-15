"""Testes para faers_bulk/timeline.py — timeline temporal via bulk."""

from __future__ import annotations

from pathlib import Path

import pytest

from hypokrates.faers_bulk.constants import RoleCodFilter
from hypokrates.faers_bulk.drug_resolver import clear_cache
from hypokrates.faers_bulk.store import FAERSBulkStore
from hypokrates.faers_bulk.timeline import bulk_signal_timeline
from hypokrates.stats.models import TimelineResult

GOLDEN_ZIP_Q3 = (
    Path(__file__).parent.parent / "golden_data" / "faers_bulk" / "faers_ascii_2024Q3.zip"
)
GOLDEN_ZIP_Q4 = (
    Path(__file__).parent.parent / "golden_data" / "faers_bulk" / "faers_ascii_2024Q4.zip"
)


@pytest.fixture()
def loaded_store(tmp_path: Path) -> FAERSBulkStore:
    """FAERSBulkStore com Q3+Q4 carregados — singleton."""
    db_path = tmp_path / "test_timeline.duckdb"
    store = FAERSBulkStore(db_path)
    store.load_quarter(GOLDEN_ZIP_Q3)
    store.load_quarter(GOLDEN_ZIP_Q4)
    FAERSBulkStore._instance = store
    clear_cache()
    yield store  # type: ignore[misc]
    FAERSBulkStore._instance = None


class TestBulkTimeline:
    """Testes de timeline via bulk."""

    async def test_basic_timeline(self, loaded_store: FAERSBulkStore) -> None:
        """Timeline retorna quarters com contagens."""
        result = await bulk_signal_timeline("propofol", "bradycardia")
        assert isinstance(result, TimelineResult)
        assert result.drug == "propofol"
        assert result.event == "bradycardia"
        assert result.total_reports > 0
        assert len(result.quarters) > 0

    async def test_meta_source(self, loaded_store: FAERSBulkStore) -> None:
        """Meta source indica bulk deduplicated."""
        result = await bulk_signal_timeline("propofol", "bradycardia")
        assert result.meta.source == "FAERS/bulk (deduplicated)"

    async def test_multiple_quarters(self, loaded_store: FAERSBulkStore) -> None:
        """Com Q3+Q4 carregados, pode ter 2 quarters."""
        result = await bulk_signal_timeline(
            "propofol", "bradycardia", role_filter=RoleCodFilter.ALL
        )
        # PROPOFOL + BRADYCARDIA aparece em Q3 e Q4
        # Q3: pids 80000003, 80000004, 80000006
        # Q4: pid 80000010
        quarter_keys = [f"{q.year}-Q{q.quarter}" for q in result.quarters]
        assert len(quarter_keys) >= 1

    async def test_role_filter(self, loaded_store: FAERSBulkStore) -> None:
        """Role filter afeta contagens."""
        all_result = await bulk_signal_timeline(
            "propofol", "bradycardia", role_filter=RoleCodFilter.ALL
        )
        suspect_result = await bulk_signal_timeline(
            "propofol", "bradycardia", role_filter=RoleCodFilter.SUSPECT
        )
        # ALL includes concomitant, so total should be >= SUSPECT
        assert all_result.total_reports >= suspect_result.total_reports

    async def test_nonexistent_drug(self, loaded_store: FAERSBulkStore) -> None:
        """Droga não existente retorna timeline vazia."""
        result = await bulk_signal_timeline("NONEXISTENT", "BRADYCARDIA")
        assert result.total_reports == 0
        assert result.quarters == []

    async def test_quarter_labels(self, loaded_store: FAERSBulkStore) -> None:
        """Quarter labels no formato correto."""
        result = await bulk_signal_timeline(
            "propofol", "bradycardia", role_filter=RoleCodFilter.ALL
        )
        for q in result.quarters:
            assert q.label == f"{q.year}-Q{q.quarter}"
