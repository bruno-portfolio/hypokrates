"""API pública do módulo FAERS — async-first."""

from __future__ import annotations

import logging
from datetime import UTC, datetime
from typing import Any

from hypokrates.faers.client import FAERSClient
from hypokrates.faers.constants import COUNT_FIELDS, SEARCH_FIELDS, SEX_MAP
from hypokrates.faers.models import FAERSResult
from hypokrates.faers.parser import parse_count_results, parse_reports
from hypokrates.models import MetaInfo

logger = logging.getLogger(__name__)


async def adverse_events(
    drug: str,
    *,
    age_min: int | None = None,
    age_max: int | None = None,
    sex: str | None = None,
    serious: bool | None = None,
    limit: int = 100,
    use_cache: bool = True,
) -> FAERSResult:
    """Busca eventos adversos reportados para um medicamento no FAERS.

    Args:
        drug: Nome genérico do medicamento (e.g., "propofol").
        age_min: Idade mínima do paciente.
        age_max: Idade máxima do paciente.
        sex: Sexo ("M", "F").
        serious: Se True, apenas reports sérios.
        limit: Máximo de reports retornados.
        use_cache: Se deve usar cache.

    Returns:
        FAERSResult com reports parseados e metadados.
    """
    search = _build_search(drug, age_min=age_min, age_max=age_max, sex=sex, serious=serious)
    query_params: dict[str, object] = {"drug": drug}
    if age_min is not None:
        query_params["age_min"] = age_min
    if age_max is not None:
        query_params["age_max"] = age_max
    if sex is not None:
        query_params["sex"] = sex
    if serious is not None:
        query_params["serious"] = serious

    client = FAERSClient()
    try:
        data = await client.fetch(search, limit=limit, use_cache=use_cache)
    finally:
        await client.close()

    raw_results: list[dict[str, Any]] = data.get("results", [])
    reports = parse_reports(raw_results)

    total = _extract_total(data)

    return FAERSResult(
        reports=reports,
        meta=MetaInfo(
            source="OpenFDA/FAERS",
            query=query_params,
            total_results=total,
            cached=False,
            retrieved_at=datetime.now(UTC),
        ),
    )


async def top_events(
    drug: str,
    *,
    limit: int = 10,
    use_cache: bool = True,
) -> FAERSResult:
    """Retorna os eventos adversos mais reportados para um medicamento.

    Args:
        drug: Nome genérico do medicamento.
        limit: Número de eventos retornados (top N).
        use_cache: Se deve usar cache.

    Returns:
        FAERSResult com eventos ordenados por contagem.
    """
    search = _build_search(drug)
    count_field = COUNT_FIELDS["reaction"]

    client = FAERSClient()
    try:
        data = await client.fetch_count(search, count_field, limit=limit, use_cache=use_cache)
    finally:
        await client.close()

    raw_results: list[dict[str, Any]] = data.get("results", [])
    events = parse_count_results(raw_results)

    return FAERSResult(
        events=events,
        meta=MetaInfo(
            source="OpenFDA/FAERS",
            query={"drug": drug, "count": "reaction", "limit": limit},
            total_results=len(events),
            retrieved_at=datetime.now(UTC),
        ),
    )


async def compare(
    drugs: list[str],
    *,
    outcome: str | None = None,
    limit: int = 10,
    use_cache: bool = True,
) -> dict[str, FAERSResult]:
    """Compara eventos adversos entre múltiplos medicamentos.

    Args:
        drugs: Lista de nomes genéricos.
        outcome: Filtrar por reação específica.
        limit: Top N eventos por droga.
        use_cache: Se deve usar cache.

    Returns:
        Dict mapeando nome da droga para seu FAERSResult.
    """
    results: dict[str, FAERSResult] = {}
    for drug in drugs:
        if outcome:
            search = _build_search(drug)
            search += f'+AND+{SEARCH_FIELDS["reaction"]}:"{outcome}"'

            client = FAERSClient()
            try:
                data = await client.fetch(search, limit=limit, use_cache=use_cache)
            finally:
                await client.close()

            raw_results: list[dict[str, Any]] = data.get("results", [])
            reports = parse_reports(raw_results)
            total = _extract_total(data)

            results[drug] = FAERSResult(
                reports=reports,
                meta=MetaInfo(
                    source="OpenFDA/FAERS",
                    query={"drug": drug, "outcome": outcome},
                    total_results=total,
                    retrieved_at=datetime.now(UTC),
                ),
            )
        else:
            results[drug] = await top_events(drug, limit=limit, use_cache=use_cache)

    return results


def _build_search(
    drug: str,
    *,
    age_min: int | None = None,
    age_max: int | None = None,
    sex: str | None = None,
    serious: bool | None = None,
) -> str:
    """Constrói query string para OpenFDA search."""
    parts: list[str] = [f'{SEARCH_FIELDS["drug"]}:"{drug.upper()}"']

    if age_min is not None and age_max is not None:
        parts.append(f"patient.patientonsetage:[{age_min}+TO+{age_max}]")
    elif age_min is not None:
        parts.append(f"patient.patientonsetage:[{age_min}+TO+999]")
    elif age_max is not None:
        parts.append(f"patient.patientonsetage:[0+TO+{age_max}]")

    if sex is not None:
        sex_code = SEX_MAP.get(sex.upper(), "0")
        parts.append(f"patient.patientsex:{sex_code}")

    if serious is not None:
        parts.append(f"serious:{'1' if serious else '2'}")

    return "+AND+".join(parts)


def _extract_total(data: dict[str, Any]) -> int:
    """Extrai total de resultados do meta OpenFDA."""
    try:
        meta = data.get("meta", {})
        results_meta = meta.get("results", {})
        return int(results_meta.get("total", 0))
    except (ValueError, TypeError):
        return 0
