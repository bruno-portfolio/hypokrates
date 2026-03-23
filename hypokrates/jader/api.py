from __future__ import annotations

import asyncio
import logging
from datetime import UTC, datetime

from hypokrates.config import get_config
from hypokrates.jader.constants import JADER_CAVEAT
from hypokrates.jader.models import JADERBulkStatus, JADERSignalResult, MappingConfidence
from hypokrates.jader.store import JADERStore
from hypokrates.models import MetaInfo
from hypokrates.stats.measures import compute_ebgm, compute_ic, compute_ror
from hypokrates.stats.models import ContingencyTable

logger = logging.getLogger(__name__)

_MIN_REPORTS = 3
_MIN_PRR = 2.0


async def _ensure_loaded(
    _store: JADERStore | None = None,
) -> JADERStore:
    """Garante que o store está carregado.

    JADER requires manual download due to PMDA CAPTCHA protection.
    Auto-download is not possible — use configure(jader_bulk_path=...).
    """
    if _store is not None:
        return _store

    store = JADERStore.get_instance()
    if store.loaded:
        return store

    config = get_config()
    if config.jader_bulk_path is None:
        from hypokrates.exceptions import ConfigurationError

        raise ConfigurationError(
            "jader_bulk_path",
            "JADER requires manual download (PMDA uses CAPTCHA). "
            "Download from https://www.pmda.go.jp/safety/info-services/"
            "drugs/adr-info/suspected-adr/0005.html then use "
            "configure(jader_bulk_path='/path/to/extracted/csvs/').",
        )

    csv_dir = str(config.jader_bulk_path)
    logger.info("JADER store not loaded — loading: %s", csv_dir)
    await asyncio.to_thread(store.load_from_csvs, csv_dir)
    return store


def _get_drug_confidence(store: JADERStore, drug: str) -> MappingConfidence:
    """Busca confidence do mapeamento da droga no store."""
    rows = store.query_in_lock(
        "SELECT drug_confidence FROM jader_drug WHERE UPPER(drug_name_en) = UPPER($1) LIMIT 1",
        [drug],
    )
    if rows and rows[0]:
        val = str(rows[0][0])
        try:
            return MappingConfidence(val)
        except ValueError:
            return MappingConfidence.UNMAPPED
    return MappingConfidence.UNMAPPED


def _get_event_confidence(store: JADERStore, event: str) -> MappingConfidence:
    """Busca confidence do mapeamento do evento no store."""
    rows = store.query_in_lock(
        "SELECT event_confidence FROM jader_reac WHERE UPPER(pt_en) = UPPER($1) LIMIT 1",
        [event],
    )
    if rows and rows[0]:
        val = str(rows[0][0])
        try:
            return MappingConfidence(val)
        except ValueError:
            return MappingConfidence.UNMAPPED
    return MappingConfidence.UNMAPPED


async def jader_signal(
    drug: str,
    event: str,
    *,
    suspect_only: bool = False,
    _store: JADERStore | None = None,
) -> JADERSignalResult:
    """Calcula PRR para drug-event no JADER.

    Args:
        drug: Nome do ingrediente ativo (EN).
        event: Termo MedDRA PT (EN).
        suspect_only: Se True, conta apenas reports onde a droga é 被疑薬 (Suspect).
        _store: Store injetado (para testes).

    Returns:
        JADERSignalResult com PRR e flag de sinal.
    """
    store = await _ensure_loaded(_store)
    a, b, c, n = await asyncio.to_thread(store.four_counts, drug, event, suspect_only=suspect_only)

    d = n - a - b - c
    table = ContingencyTable(a=a, b=b, c=c, d=d)

    prr = 0.0
    if a > 0 and (a + b) > 0 and (c + d) > 0 and c > 0:
        prr = (a / (a + b)) / (c / (c + d))

    ror_result = compute_ror(table)
    ic_result = compute_ic(table)
    ebgm_result = compute_ebgm(table)

    prr_sig = a >= _MIN_REPORTS and prr >= _MIN_PRR
    sig_count = sum([prr_sig, ror_result.significant, ic_result.significant])
    signal_detected = sig_count >= 2

    drug_conf = await asyncio.to_thread(_get_drug_confidence, store, drug)
    event_conf = await asyncio.to_thread(_get_event_confidence, store, event)

    caveat = JADER_CAVEAT
    if drug_conf != MappingConfidence.EXACT or event_conf != MappingConfidence.EXACT:
        caveat += f" Mapping confidence: drug={drug_conf.value}, event={event_conf.value}."

    return JADERSignalResult(
        drug=drug,
        event=event,
        drug_confidence=drug_conf,
        event_confidence=event_conf,
        drug_event_count=a,
        drug_total=a + b,
        event_total=a + c,
        total_reports=n,
        prr=round(prr, 2),
        ror=round(ror_result.value, 2),
        ic=round(ic_result.value, 2),
        ebgm=round(ebgm_result.value, 2),
        signal_detected=signal_detected,
        table=table,
        meta=MetaInfo(
            source="JADER (PMDA)",
            query={"drug": drug, "event": event, "suspect_only": suspect_only},
            total_results=a,
            retrieved_at=datetime.now(UTC),
            disclaimer=caveat,
        ),
    )


async def jader_top_events(
    drug: str,
    *,
    limit: int = 10,
    suspect_only: bool = False,
    _store: JADERStore | None = None,
) -> list[tuple[str, int]]:
    """Retorna top eventos adversos para uma droga no JADER.

    Args:
        drug: Nome do ingrediente ativo (EN).
        limit: Máximo de eventos.
        suspect_only: Se True, conta apenas Suspect (被疑薬).
        _store: Store injetado (para testes).

    Returns:
        Lista de (event_term, count) ordenada por count DESC.
    """
    store = await _ensure_loaded(_store)
    return await asyncio.to_thread(store.top_events, drug, suspect_only=suspect_only, limit=limit)


async def jader_bulk_status(
    *,
    _store: JADERStore | None = None,
) -> JADERBulkStatus:
    """Retorna status do JADER store.

    Args:
        _store: Store injetado (para testes).

    Returns:
        JADERBulkStatus com contagens, data range e mapping stats.
    """
    store = await _ensure_loaded(_store)

    total_reports = await asyncio.to_thread(store.count_reports)
    total_drugs = await asyncio.to_thread(store.count_drugs)
    total_reactions = await asyncio.to_thread(store.count_reactions)
    date_range = await asyncio.to_thread(store.date_range)
    m_stats = await asyncio.to_thread(store.mapping_stats)

    return JADERBulkStatus(
        loaded=True,
        total_reports=total_reports,
        total_drugs=total_drugs,
        total_reactions=total_reactions,
        date_range=date_range,
        exact_drug_mappings=m_stats["exact_drugs"],
        inferred_drug_mappings=m_stats["inferred_drugs"],
        unmapped_drugs=m_stats["unmapped_drugs"],
        exact_event_mappings=m_stats["exact_events"],
        inferred_event_mappings=m_stats["inferred_events"],
        unmapped_events=m_stats["unmapped_events"],
        meta=MetaInfo(
            source="JADER (PMDA)",
            query={"action": "status"},
            total_results=total_reports,
            retrieved_at=datetime.now(UTC),
            disclaimer=JADER_CAVEAT,
        ),
    )
