"""API pública do módulo FAERS — async-first."""

from __future__ import annotations

import logging
import statistics
from collections import Counter
from datetime import UTC, datetime
from typing import Any

from hypokrates.faers.client import FAERSClient
from hypokrates.faers.constants import (
    CO_ADMIN_SAMPLE_SIZE,
    CO_ADMIN_THRESHOLD,
    CO_ADMIN_TOP_DRUGS,
    COUNT_FIELDS,
    DRUG_CHARACTERIZATION_FIELD,
    DRUG_CHARACTERIZATION_SUSPECT,
    DRUG_FIELD_FALLBACK,
    SEARCH_FIELDS,
    SEX_MAP,
)
from hypokrates.faers.models import CoSuspectProfile, DrugsByEventResult, FAERSResult
from hypokrates.faers.parser import parse_count_results, parse_drug_count_results, parse_reports
from hypokrates.models import MetaInfo

# Cache in-memory da resolução de campo por droga (vive enquanto o processo vive)
_drug_field_cache: dict[str, str] = {}

logger = logging.getLogger(__name__)


async def adverse_events(
    drug: str,
    *,
    age_min: int | None = None,
    age_max: int | None = None,
    sex: str | None = None,
    serious: bool | None = None,
    suspect_only: bool = False,
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
        suspect_only: Se True, apenas reports onde a droga é suspect (não concomitante).
        limit: Máximo de reports retornados.
        use_cache: Se deve usar cache.

    Returns:
        FAERSResult com reports parseados e metadados.
    """
    client = FAERSClient()
    try:
        drug_search = await resolve_drug_field(drug, client=client, use_cache=use_cache)
        search = _build_search(
            drug,
            drug_search=drug_search,
            age_min=age_min,
            age_max=age_max,
            sex=sex,
            serious=serious,
            suspect_only=suspect_only,
        )
        data = await client.fetch(search, limit=limit, use_cache=use_cache)
    finally:
        await client.close()

    query_params: dict[str, object] = {"drug": drug}
    if age_min is not None:
        query_params["age_min"] = age_min
    if age_max is not None:
        query_params["age_max"] = age_max
    if sex is not None:
        query_params["sex"] = sex
    if serious is not None:
        query_params["serious"] = serious

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
    suspect_only: bool = False,
    limit: int = 10,
    use_cache: bool = True,
) -> FAERSResult:
    """Retorna os eventos adversos mais reportados para um medicamento.

    Args:
        drug: Nome genérico do medicamento.
        suspect_only: Se True, apenas reports onde a droga é suspect.
        limit: Número de eventos retornados (top N).
        use_cache: Se deve usar cache.

    Returns:
        FAERSResult com eventos ordenados por contagem.
    """
    client = FAERSClient()
    try:
        drug_search = await resolve_drug_field(drug, client=client, use_cache=use_cache)
        search = _build_search(drug, drug_search=drug_search, suspect_only=suspect_only)
        count_field = COUNT_FIELDS["reaction"]
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
            client = FAERSClient()
            try:
                drug_search = await resolve_drug_field(drug, client=client, use_cache=use_cache)
                search = _build_search(drug, drug_search=drug_search)
                search += f' AND {SEARCH_FIELDS["reaction"]}:"{outcome}"'
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


async def drugs_by_event(
    event: str,
    *,
    suspect_only: bool = False,
    limit: int = 10,
    use_cache: bool = True,
) -> DrugsByEventResult:
    """Retorna os medicamentos mais reportados para um evento adverso (reverse lookup).

    Args:
        event: Termo MedDRA do evento adverso (e.g., "anaphylactic shock").
        suspect_only: Se True, apenas reports onde a droga e suspect.
        limit: Numero de drogas retornadas (top N).
        use_cache: Se deve usar cache.

    Returns:
        DrugsByEventResult com drogas ordenadas por contagem de reports.
    """
    client = FAERSClient()
    try:
        search = _build_event_search(event, suspect_only=suspect_only)
        count_field = COUNT_FIELDS["drug"]
        data = await client.fetch_count(search, count_field, limit=limit, use_cache=use_cache)
    finally:
        await client.close()

    raw_results: list[dict[str, Any]] = data.get("results", [])
    drugs = parse_drug_count_results(raw_results)

    return DrugsByEventResult(
        event=event.upper(),
        drugs=drugs,
        meta=MetaInfo(
            source="OpenFDA/FAERS",
            query={"event": event, "count": "drug", "limit": limit},
            total_results=len(drugs),
            retrieved_at=datetime.now(UTC),
        ),
    )


async def co_suspect_profile(
    drug: str,
    event: str,
    *,
    sample_size: int = CO_ADMIN_SAMPLE_SIZE,
    suspect_only: bool = False,
    use_cache: bool = True,
    _client: FAERSClient | None = None,
    _drug_search: str | None = None,
) -> CoSuspectProfile:
    """Analisa padrões de co-suspects em reports de um par droga+evento.

    Busca uma amostra de reports individuais e conta quantos outros
    medicamentos são listados como suspect nos mesmos reports.
    Mediana alta (>3) indica setting procedimental (ex: centro cirúrgico)
    onde o PRR pode ser inflado por co-administração, não por causalidade.

    Args:
        drug: Nome genérico do medicamento.
        event: Termo MedDRA do evento adverso.
        sample_size: Nº de reports para amostrar (1 API call).
        suspect_only: Se True, filtra apenas reports onde a droga é suspect.
        use_cache: Se deve usar cache.
        _client: FAERSClient reutilizável (evita criar novo).
        _drug_search: Query de droga pré-resolvida (evita resolução redundante).

    Returns:
        CoSuspectProfile com estatísticas de co-administração.
    """
    own_client = _client is None
    client = _client if _client is not None else FAERSClient()

    try:
        drug_search = _drug_search or await resolve_drug_field(
            drug, client=client, use_cache=use_cache
        )
        reaction_field = f'{SEARCH_FIELDS["reaction"]}:"{event.upper()}"'
        search = f"{drug_search} AND {reaction_field}"
        if suspect_only:
            search += f" AND {DRUG_CHARACTERIZATION_FIELD}:{DRUG_CHARACTERIZATION_SUSPECT}"

        data = await client.fetch(search, limit=sample_size, use_cache=use_cache)
    finally:
        if own_client:
            await client.close()

    raw_results: list[dict[str, Any]] = data.get("results", [])
    reports = parse_reports(raw_results)

    if not reports:
        return CoSuspectProfile(drug=drug.upper(), event=event.upper())

    drug_upper = drug.upper()
    suspect_counts: list[int] = []
    co_drug_counter: Counter[str] = Counter()

    for report in reports:
        suspects = [d for d in report.drugs if d.role == DRUG_CHARACTERIZATION_SUSPECT]
        suspect_counts.append(len(suspects))
        for d in suspects:
            co_name = d.name.upper()
            # Excluir a droga-índice E salt forms (ex: ONDANSETRON HYDROCHLORIDE)
            if co_name == drug_upper:
                continue
            if co_name.startswith(drug_upper + " ") or drug_upper.startswith(co_name + " "):
                continue
            co_drug_counter[co_name] += 1

    median_val = statistics.median(suspect_counts)
    mean_val = statistics.mean(suspect_counts)
    max_val = max(suspect_counts)

    return CoSuspectProfile(
        drug=drug_upper,
        event=event.upper(),
        sample_size=len(reports),
        median_suspects=median_val,
        mean_suspects=round(mean_val, 2),
        max_suspects=max_val,
        top_co_drugs=co_drug_counter.most_common(CO_ADMIN_TOP_DRUGS),
        co_admin_flag=median_val > CO_ADMIN_THRESHOLD,
    )


async def resolve_drug_field(
    drug: str,
    *,
    client: FAERSClient | None = None,
    use_cache: bool = True,
) -> str:
    """Resolve qual campo OpenFDA tem dados para uma droga.

    Tenta generic_name.exact → brand_name.exact → medicinalproduct.
    Se não encontrar, tenta normalizar brand→generic via RxNorm e retenta.
    Resultado cacheado em memória por droga.

    Args:
        drug: Nome da droga.
        client: FAERSClient opcional (reutiliza se fornecido).
        use_cache: Se deve usar cache nas queries de resolução.

    Returns:
        Search fragment (ex: 'patient.drug.openfda.generic_name.exact:"PROPOFOL"').
    """
    drug_upper = drug.upper()
    if drug_upper in _drug_field_cache:
        return _drug_field_cache[drug_upper]

    own_client = client is None
    resolved_client = client if client is not None else FAERSClient()

    try:
        # 1. Tentar generic_name.exact com o input direto
        generic_field = SEARCH_FIELDS["drug"]
        search = f'{generic_field}:"{drug_upper}"'
        total = await resolved_client.fetch_total(search, use_cache=use_cache)
        if total > 0:
            _drug_field_cache[drug_upper] = search
            logger.info("Resolved %s -> generic_name.exact (%d reports)", drug, total)
            return search

        # 2. Normalizar brand→generic via RxNorm ANTES de tentar outros campos
        try:
            from hypokrates.vocab.api import normalize_drug

            norm = await normalize_drug(drug, use_cache=use_cache)
            if norm.generic_name and norm.generic_name.upper() != drug_upper:
                generic_upper = norm.generic_name.upper()
                # Checar se o generic_name já está no cache
                if generic_upper in _drug_field_cache:
                    result = _drug_field_cache[generic_upper]
                    _drug_field_cache[drug_upper] = result
                    logger.info("Resolved %s -> %s (via normalize_drug)", drug, norm.generic_name)
                    return result
                # Tentar generic_name normalizado no FAERS
                generic_search = f'{generic_field}:"{generic_upper}"'
                total = await resolved_client.fetch_total(generic_search, use_cache=use_cache)
                if total > 0:
                    _drug_field_cache[drug_upper] = generic_search
                    _drug_field_cache[generic_upper] = generic_search
                    logger.info(
                        "Resolved %s -> generic_name %s (%d reports)",
                        drug,
                        norm.generic_name,
                        total,
                    )
                    return generic_search
        except Exception:
            logger.debug("normalize_drug failed for %s", drug)

        # 3. Fallback: brand_name.exact e medicinalproduct (último recurso)
        for field in DRUG_FIELD_FALLBACK[1:]:  # skip generic_name (já tentou)
            search = f'{field}:"{drug_upper}"'
            total = await resolved_client.fetch_total(search, use_cache=use_cache)
            if total > 0:
                _drug_field_cache[drug_upper] = search
                logger.info("Resolved %s -> %s (%d reports)", drug, field, total)
                return search
    finally:
        if own_client:
            await resolved_client.close()

    # Nenhum campo retornou resultados — usar generic_name como fallback
    fallback = f'{SEARCH_FIELDS["drug"]}:"{drug_upper}"'
    _drug_field_cache[drug_upper] = fallback
    logger.warning("No FAERS data found for %s in any field", drug)
    return fallback


def _build_search(
    drug: str,
    *,
    drug_search: str | None = None,
    age_min: int | None = None,
    age_max: int | None = None,
    sex: str | None = None,
    serious: bool | None = None,
    suspect_only: bool = False,
) -> str:
    """Constrói query string para OpenFDA search."""
    parts: list[str] = [drug_search or f'{SEARCH_FIELDS["drug"]}:"{drug.upper()}"']

    if suspect_only:
        parts.append(f"{DRUG_CHARACTERIZATION_FIELD}:{DRUG_CHARACTERIZATION_SUSPECT}")

    if age_min is not None and age_max is not None:
        parts.append(f"patient.patientonsetage:[{age_min} TO {age_max}]")
    elif age_min is not None:
        parts.append(f"patient.patientonsetage:[{age_min} TO 999]")
    elif age_max is not None:
        parts.append(f"patient.patientonsetage:[0 TO {age_max}]")

    if sex is not None:
        sex_code = SEX_MAP.get(sex.upper(), "0")
        parts.append(f"patient.patientsex:{sex_code}")

    if serious is not None:
        parts.append(f"serious:{'1' if serious else '2'}")

    return " AND ".join(parts)


def _build_event_search(
    event: str,
    *,
    suspect_only: bool = False,
) -> str:
    """Constroi query string para busca por evento adverso (reverse lookup).

    Expande o evento via MedDRA para incluir sinônimos (ex: "malignant hyperthermia"
    também busca "hyperthermia malignant").
    """
    from hypokrates.vocab.meddra import expand_event_terms

    reaction_field = SEARCH_FIELDS["reaction"]
    terms = expand_event_terms(event)
    if len(terms) == 1:
        reaction_query = f'{reaction_field}:"{terms[0]}"'
    else:
        reaction_parts = [f'{reaction_field}:"{t}"' for t in terms]
        reaction_query = "(" + " ".join(reaction_parts) + ")"

    parts: list[str] = [reaction_query]
    if suspect_only:
        parts.append(f"{DRUG_CHARACTERIZATION_FIELD}:{DRUG_CHARACTERIZATION_SUSPECT}")
    return " AND ".join(parts)


def _extract_total(data: dict[str, Any]) -> int:
    """Extrai total de resultados do meta OpenFDA."""
    try:
        meta = data.get("meta", {})
        results_meta = meta.get("results", {})
        return int(results_meta.get("total", 0))
    except (ValueError, TypeError):
        return 0
