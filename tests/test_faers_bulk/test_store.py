"""Testes para faers_bulk/store.py — DuckDB store com deduplicação."""

from __future__ import annotations

from pathlib import Path

import pytest

from hypokrates.faers_bulk.constants import RoleCodFilter
from hypokrates.faers_bulk.store import FAERSBulkStore

GOLDEN_ZIP_Q3 = (
    Path(__file__).parent.parent / "golden_data" / "faers_bulk" / "faers_ascii_2024Q3.zip"
)
GOLDEN_ZIP_Q4 = (
    Path(__file__).parent.parent / "golden_data" / "faers_bulk" / "faers_ascii_2024Q4.zip"
)


@pytest.fixture()
def store(tmp_path: Path) -> FAERSBulkStore:
    """FAERSBulkStore em diretório temporário."""
    db_path = tmp_path / "test_faers_bulk.duckdb"
    return FAERSBulkStore(db_path)


@pytest.fixture()
def loaded_store(store: FAERSBulkStore) -> FAERSBulkStore:
    """FAERSBulkStore com Q3 já carregado."""
    store.load_quarter(GOLDEN_ZIP_Q3)
    return store


class TestFAERSBulkStoreBasic:
    """Testes básicos do store."""

    def test_empty_store_not_loaded(self, store: FAERSBulkStore) -> None:
        assert store.is_loaded() is False

    def test_load_quarter(self, store: FAERSBulkStore) -> None:
        count = store.load_quarter(GOLDEN_ZIP_Q3)
        assert count == 9  # 9 demo rows
        assert store.is_loaded() is True

    def test_load_idempotent(self, loaded_store: FAERSBulkStore) -> None:
        """Carregar mesmo quarter 2x deve skip na segunda vez."""
        count = loaded_store.load_quarter(GOLDEN_ZIP_Q3)
        assert count == 0  # skipped

    def test_load_force(self, loaded_store: FAERSBulkStore) -> None:
        """force=True recarrega."""
        count = loaded_store.load_quarter(GOLDEN_ZIP_Q3, force=True)
        assert count == 9

    def test_close(self, store: FAERSBulkStore) -> None:
        store.close()

    def test_singleton_reset(self) -> None:
        FAERSBulkStore.reset()
        assert FAERSBulkStore._instance is None


class TestDedup:
    """Testes de deduplicação por CASEID."""

    def test_dedup_count(self, loaded_store: FAERSBulkStore) -> None:
        """9 reports com 5 caseids únicos → 5 deduped."""
        count = loaded_store.count_total()
        assert count == 5

    def test_rebuild_dedup(self, loaded_store: FAERSBulkStore) -> None:
        count = loaded_store.rebuild_dedup()
        assert count == 5

    def test_dedup_keeps_max_caseversion(self, loaded_store: FAERSBulkStore) -> None:
        """Verifica que dedup mantém a versão mais recente.

        CASEID 100001 tem v1 (pid 80000001), v2 (pid 80000002), v3 (pid 80000003).
        Dedup deve manter pid 80000003.
        """
        # Query direta no DuckDB para validar
        with loaded_store._db_lock:
            result = loaded_store._conn.execute(
                "SELECT primaryid, caseversion FROM faers_dedup WHERE caseid = '100001'"
            ).fetchone()
        assert result is not None
        assert result[0] == "80000003"  # primaryid da v3
        assert result[1] == 3  # caseversion


class TestFourCounts:
    """Testes de four_counts (contagens deduplicadas)."""

    def test_propofol_bradycardia_suspect(self, loaded_store: FAERSBulkStore) -> None:
        """PROPOFOL + BRADYCARDIA com role SUSPECT (PS+SS).

        Deduped PIDs com PROPOFOL suspect: 80000003 (PS), 80000004 (SS), 80000005 (PS)
        Deduped PIDs com BRADYCARDIA: 80000003, 80000004, 80000006
        Intersection (a): 80000003, 80000004 → 2
        """
        result = loaded_store.four_counts(
            "propofol", "bradycardia", role_filter=RoleCodFilter.SUSPECT
        )
        assert result.drug_event == 2  # a
        assert result.drug_total == 3  # a+b (3 PIDs com PROPOFOL suspect)
        assert result.event_total == 3  # a+c (3 PIDs com BRADYCARDIA)
        assert result.n_total == 5  # N deduped
        assert result.deduped is True

    def test_propofol_bradycardia_ps_only(self, loaded_store: FAERSBulkStore) -> None:
        """PROPOFOL + BRADYCARDIA com PS_ONLY.

        Deduped PIDs com PROPOFOL PS-only: 80000003 (PS), 80000005 (PS)
        (80000004 é SS, não conta)
        Deduped PIDs com BRADYCARDIA: 80000003, 80000004, 80000006
        Intersection (a): 80000003 → 1
        """
        result = loaded_store.four_counts(
            "propofol", "bradycardia", role_filter=RoleCodFilter.PS_ONLY
        )
        assert result.drug_event == 1  # a
        assert result.drug_total == 2  # 80000003 + 80000005
        assert result.event_total == 3  # unchanged
        assert result.n_total == 5

    def test_propofol_bradycardia_all(self, loaded_store: FAERSBulkStore) -> None:
        """PROPOFOL + BRADYCARDIA com ALL (inclui Concomitant).

        Deduped PIDs com PROPOFOL any role:
        80000003 (PS), 80000004 (SS), 80000005 (PS), 80000006 (C)
        Deduped PIDs com BRADYCARDIA: 80000003, 80000004, 80000006
        Intersection (a): 80000003, 80000004, 80000006 → 3
        """
        result = loaded_store.four_counts("propofol", "bradycardia", role_filter=RoleCodFilter.ALL)
        assert result.drug_event == 3  # a
        assert result.drug_total == 4  # 4 PIDs com PROPOFOL qualquer role
        assert result.event_total == 3
        assert result.n_total == 5

    def test_fentanyl_bradycardia(self, loaded_store: FAERSBulkStore) -> None:
        """FENTANYL + BRADYCARDIA — drugname normalizado via Tier 2.

        pid 80000006 tem drugname "FENTANYL 50MCG", prod_ai vazio → normaliza para "FENTANYL"
        pid 80000004 tem drugname "FENTANYL CITRATE", prod_ai vazio
        → normaliza para "FENTANYL CITRATE"
        São nomes diferentes, queries separadas.
        """
        # FENTANYL CITRATE (pid 80000004) != FENTANYL (pid 80000006)
        # Eles normalizam diferente: "FENTANYL CITRATE" vs "FENTANYL"
        result_citrate = loaded_store.four_counts("fentanyl citrate", "bradycardia")
        assert result_citrate.drug_event == 1  # pid 80000004

        result_plain = loaded_store.four_counts("fentanyl", "bradycardia")
        assert result_plain.drug_event == 1  # pid 80000006

    def test_nonexistent_drug(self, loaded_store: FAERSBulkStore) -> None:
        """Droga não existente retorna zeros."""
        result = loaded_store.four_counts("NONEXISTENT_DRUG", "BRADYCARDIA")
        assert result.drug_event == 0
        assert result.drug_total == 0
        assert result.n_total == 5  # N sempre retorna total

    def test_case_insensitive(self, loaded_store: FAERSBulkStore) -> None:
        """Busca é case-insensitive."""
        upper = loaded_store.four_counts("PROPOFOL", "BRADYCARDIA")
        lower = loaded_store.four_counts("propofol", "bradycardia")
        mixed = loaded_store.four_counts("Propofol", "Bradycardia")
        assert upper.drug_event == lower.drug_event == mixed.drug_event


class TestTopEvents:
    """Testes para top_events() — eventos mais reportados deduplicados."""

    def test_top_events_suspect(self, loaded_store: FAERSBulkStore) -> None:
        """Top events para PROPOFOL com SUSPECT (PS+SS)."""
        events = loaded_store.top_events("propofol", role_filter=RoleCodFilter.SUSPECT)
        assert len(events) > 0
        # Cada item é (event_term, count)
        assert all(isinstance(e, tuple) and len(e) == 2 for e in events)
        # BRADYCARDIA deve estar nos resultados (3 PIDs com PROPOFOL suspect, 2 com BRADYCARDIA)
        event_names = [e[0] for e in events]
        assert "BRADYCARDIA" in event_names

    def test_top_events_ps_only(self, loaded_store: FAERSBulkStore) -> None:
        """Top events com PS_ONLY retorna menos resultados."""
        suspect = loaded_store.top_events("propofol", role_filter=RoleCodFilter.SUSPECT)
        ps_only = loaded_store.top_events("propofol", role_filter=RoleCodFilter.PS_ONLY)
        # PS_ONLY deve ter contagens menores ou iguais
        suspect_dict = dict(suspect)
        ps_dict = dict(ps_only)
        for ev in ps_dict:
            if ev in suspect_dict:
                assert ps_dict[ev] <= suspect_dict[ev]

    def test_top_events_limit(self, loaded_store: FAERSBulkStore) -> None:
        """Limit clamps resultado."""
        events = loaded_store.top_events("propofol", limit=1)
        assert len(events) <= 1

    def test_top_events_ordered_by_count_desc(self, loaded_store: FAERSBulkStore) -> None:
        """Resultados vêm ordenados por count DESC."""
        events = loaded_store.top_events("propofol")
        counts = [e[1] for e in events]
        assert counts == sorted(counts, reverse=True)

    def test_top_events_nonexistent_drug(self, loaded_store: FAERSBulkStore) -> None:
        """Droga inexistente retorna lista vazia."""
        events = loaded_store.top_events("NONEXISTENT_DRUG")
        assert events == []

    def test_top_events_case_insensitive(self, loaded_store: FAERSBulkStore) -> None:
        """Busca case-insensitive (mesmos eventos e contagens)."""
        upper = loaded_store.top_events("PROPOFOL")
        lower = loaded_store.top_events("propofol")
        assert set(upper) == set(lower)


class TestDrugTotal:
    """Testes para drug_total() — total de cases dedup com a droga."""

    def test_propofol_suspect(self, loaded_store: FAERSBulkStore) -> None:
        """PROPOFOL SUSPECT (PS+SS): 3 PIDs deduped."""
        total = loaded_store.drug_total("propofol", role_filter=RoleCodFilter.SUSPECT)
        assert total == 3

    def test_propofol_ps_only(self, loaded_store: FAERSBulkStore) -> None:
        """PROPOFOL PS_ONLY: 2 PIDs deduped."""
        total = loaded_store.drug_total("propofol", role_filter=RoleCodFilter.PS_ONLY)
        assert total == 2

    def test_propofol_all(self, loaded_store: FAERSBulkStore) -> None:
        """PROPOFOL ALL: 4 PIDs deduped (PS+SS+C)."""
        total = loaded_store.drug_total("propofol", role_filter=RoleCodFilter.ALL)
        assert total == 4

    def test_nonexistent_drug(self, loaded_store: FAERSBulkStore) -> None:
        """Droga inexistente retorna 0."""
        total = loaded_store.drug_total("NONEXISTENT_DRUG")
        assert total == 0


class TestStatus:
    """Testes de status e metadados."""

    def test_get_status_empty(self, store: FAERSBulkStore) -> None:
        status = store.get_status()
        assert status.total_reports == 0
        assert status.deduped_cases == 0
        assert status.quarters_loaded == []

    def test_get_status_loaded(self, loaded_store: FAERSBulkStore) -> None:
        status = loaded_store.get_status()
        assert status.total_reports == 9
        assert status.deduped_cases == 5
        assert len(status.quarters_loaded) == 1
        assert status.oldest_quarter == "2024Q3"
        assert status.newest_quarter == "2024Q3"

    def test_get_loaded_quarters(self, loaded_store: FAERSBulkStore) -> None:
        quarters = loaded_store.get_loaded_quarters()
        assert len(quarters) == 1
        q = quarters[0]
        assert q.quarter_key == "2024Q3"
        assert q.year == 2024
        assert q.quarter == 3
        assert q.demo_count == 9
        assert q.drug_count == 12
        assert q.reac_count == 11

    def test_count_total(self, loaded_store: FAERSBulkStore) -> None:
        assert loaded_store.count_total() == 5


class TestMultiQuarter:
    """Testes com múltiplos quarters."""

    def test_load_two_quarters(self, loaded_store: FAERSBulkStore) -> None:
        """Carregar Q3 + Q4 deve ter 6 deduped cases.

        Q4 adiciona caseid 100006 (novo) + caseid 100001 v4 (update).
        Dedup: 100001 agora aponta para pid 80000010 (v4 > v3).
        Total: 5 originais + 1 novo - 0 removidos = 6.
        """
        loaded_store.load_quarter(GOLDEN_ZIP_Q4)
        assert loaded_store.count_total() == 6

    def test_dedup_across_quarters(self, loaded_store: FAERSBulkStore) -> None:
        """Dedup cross-quarter: CASEID 100001 v4 (Q4) > v3 (Q3)."""
        loaded_store.load_quarter(GOLDEN_ZIP_Q4)

        with loaded_store._db_lock:
            result = loaded_store._conn.execute(
                "SELECT primaryid, caseversion FROM faers_dedup WHERE caseid = '100001'"
            ).fetchone()
        assert result is not None
        assert result[0] == "80000010"  # v4 do Q4
        assert result[1] == 4

    def test_status_two_quarters(self, loaded_store: FAERSBulkStore) -> None:
        loaded_store.load_quarter(GOLDEN_ZIP_Q4)
        status = loaded_store.get_status()
        assert len(status.quarters_loaded) == 2
        assert status.oldest_quarter == "2024Q3"
        assert status.newest_quarter == "2024Q4"
