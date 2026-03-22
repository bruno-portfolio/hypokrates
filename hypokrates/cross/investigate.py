"""investigate() — hipótese completa + estratificação demográfica."""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Awaitable, Callable
from datetime import UTC, datetime
from typing import TYPE_CHECKING

from hypokrates.cross.api import hypothesis
from hypokrates.cross.constants import STRATUM_AGE_NOTABLE_RATIO, STRATUM_SEX_NOTABLE_RATIO
from hypokrates.cross.models import HypothesisResult, InvestigationResult, StratumSignal
from hypokrates.models import MetaInfo

if TYPE_CHECKING:
    from hypokrates.faers_bulk.models import StrataFilter

logger = logging.getLogger(__name__)

# Tipo para funções de query de strata (FAERS bulk_signal, Canada canada_signal)
_StrataQueryFn = Callable[[str, str, "StrataFilter"], Awaitable[StratumSignal]]


async def investigate(
    drug: str,
    event: str,
    *,
    suspect_only: bool = False,
    use_cache: bool = True,
) -> InvestigationResult:
    """Investigação profunda: hypothesis completa + estratificação demográfica.

    Roda em paralelo:
    1. hypothesis() com todos os enrichments
    2. FAERS Bulk strata (2 sex + 4 age groups)
    3. Canada Vigilance strata (2 sex)

    Country strata: extraído do resultado do hypothesis (FAERS/Canada/JADER).

    Args:
        drug: Nome genérico do medicamento.
        event: Termo MedDRA do evento adverso.
        suspect_only: Se True, conta apenas reports com droga suspect.
        use_cache: Se deve usar cache.

    Returns:
        InvestigationResult com hypothesis + strata + summary.
    """
    start = datetime.now(UTC)

    hyp_result, faers_strata, canada_strata = await asyncio.gather(
        hypothesis(
            drug,
            event,
            check_label=True,
            check_trials=True,
            check_drugbank=True,
            check_opentargets=True,
            check_chembl=True,
            check_coadmin=True,
            check_onsides=True,
            check_pharmgkb=True,
            check_canada=True,
            check_jader=True,
            suspect_only=suspect_only,
            use_cache=use_cache,
        ),
        _run_faers_strata(drug, event, suspect_only=suspect_only),
        _run_canada_strata(drug, event, suspect_only=suspect_only),
        return_exceptions=True,
    )

    # hypothesis é obrigatório
    if isinstance(hyp_result, BaseException):
        raise hyp_result

    faers_list: list[StratumSignal] = faers_strata if isinstance(faers_strata, list) else []
    canada_list: list[StratumSignal] = canada_strata if isinstance(canada_strata, list) else []

    # Separar por tipo
    sex_strata = [s for s in faers_list if s.stratum_type == "sex"]
    sex_strata.extend(canada_list)
    age_strata = [s for s in faers_list if s.stratum_type == "age_group"]

    # Country strata: do hypothesis result
    country_strata = _build_country_strata(hyp_result)

    # Summary textual
    demographic_summary = _build_demographic_summary(sex_strata, age_strata, country_strata)

    elapsed = (datetime.now(UTC) - start).total_seconds()

    return InvestigationResult(
        hypothesis=hyp_result,
        sex_strata=sex_strata,
        age_strata=age_strata,
        country_strata=country_strata,
        demographic_summary=demographic_summary,
        meta=MetaInfo(
            source="hypokrates/investigate",
            query={"drug": drug, "event": event, "suspect_only": suspect_only},
            total_results=hyp_result.signal.table.a,
            retrieved_at=datetime.now(UTC),
            disclaimer=(
                "Deep investigation combining hypothesis analysis with "
                "demographic stratification. Stratified PRR may have "
                "insufficient data in small subgroups."
            ),
            fetch_duration_ms=int(elapsed * 1000),
        ),
    )


async def _run_strata_batch(
    source: str,
    strata_configs: list[tuple[str, str, StrataFilter]],
    query_fn: _StrataQueryFn,
) -> list[StratumSignal]:
    """Roda batch de strata queries em paralelo via asyncio.gather.

    Args:
        source: Nome da fonte ("FAERS", "Canada").
        strata_configs: Lista de (stratum_type, stratum_value, StrataFilter).
        query_fn: Async callable(drug, event, strata) → StratumSignal.

    Returns:
        Lista de StratumSignal (com insufficient_data=True em caso de erro).
    """

    async def _safe_query(stype: str, sval: str, sf: StrataFilter) -> StratumSignal:
        try:
            return await query_fn(stype, sval, sf)
        except Exception:
            logger.debug("%s strata %s=%s failed", source, stype, sval)
            return StratumSignal(
                source=source,
                stratum_type=stype,
                stratum_value=sval,
                insufficient_data=True,
            )

    results = await asyncio.gather(
        *[_safe_query(stype, sval, sf) for stype, sval, sf in strata_configs]
    )
    return list(results)


async def _run_faers_strata(
    drug: str,
    event: str,
    *,
    suspect_only: bool = False,
) -> list[StratumSignal]:
    """Roda 6 FAERS Bulk strata queries (2 sex + 4 age groups)."""
    from hypokrates.faers_bulk import api as bulk_api
    from hypokrates.faers_bulk.constants import RoleCodFilter
    from hypokrates.faers_bulk.models import StrataFilter

    if not await bulk_api.is_bulk_available():
        return []

    role = RoleCodFilter.SUSPECT if suspect_only else RoleCodFilter.ALL

    async def _query(stype: str, sval: str, sf: StrataFilter) -> StratumSignal:
        sig = await bulk_api.bulk_signal(drug, event, role_filter=role, strata=sf)
        return StratumSignal(
            source="FAERS",
            stratum_type=stype,
            stratum_value=sval,
            drug_event_count=sig.table.a,
            prr=round(sig.prr.value, 2),
            ror=round(sig.ror.value, 2),
            ic=round(sig.ic.value, 2),
            signal_detected=sig.signal_detected,
        )

    return await _run_strata_batch(
        "FAERS",
        [
            ("sex", "M", StrataFilter(sex="M")),
            ("sex", "F", StrataFilter(sex="F")),
            ("age_group", "0-17", StrataFilter(age_group="0-17")),
            ("age_group", "18-44", StrataFilter(age_group="18-44")),
            ("age_group", "45-64", StrataFilter(age_group="45-64")),
            ("age_group", "65+", StrataFilter(age_group="65+")),
        ],
        _query,
    )


async def _run_canada_strata(
    drug: str,
    event: str,
    *,
    suspect_only: bool = False,
) -> list[StratumSignal]:
    """Roda Canada Vigilance sex strata (2 queries)."""
    from hypokrates.faers_bulk.models import StrataFilter

    async def _query(stype: str, sval: str, sf: StrataFilter) -> StratumSignal:
        from hypokrates.canada import api as canada_api

        sig = await canada_api.canada_signal(drug, event, suspect_only=suspect_only, strata=sf)
        return StratumSignal(
            source="Canada",
            stratum_type=stype,
            stratum_value=sval,
            drug_event_count=sig.drug_event_count,
            prr=round(sig.prr, 2),
            ror=round(sig.ror, 2),
            ic=round(sig.ic, 2),
            signal_detected=sig.signal_detected,
        )

    return await _run_strata_batch(
        "Canada",
        [
            ("sex", "M", StrataFilter(sex="M")),
            ("sex", "F", StrataFilter(sex="F")),
        ],
        _query,
    )


def _build_country_strata(hyp: HypothesisResult) -> list[StratumSignal]:
    """Extrai comparação cross-country do resultado do hypothesis."""
    strata: list[StratumSignal] = []

    # FAERS (sempre disponível)
    strata.append(
        StratumSignal(
            source="FAERS",
            stratum_type="country",
            stratum_value="FAERS",
            drug_event_count=hyp.signal.table.a,
            prr=round(hyp.signal.prr.value, 2),
            ror=round(hyp.signal.ror.value, 2),
            ic=round(hyp.signal.ic.value, 2),
            signal_detected=hyp.signal.signal_detected,
        )
    )

    # Canada (do hypothesis result)
    if hyp.canada_reports is not None:
        strata.append(
            StratumSignal(
                source="Canada",
                stratum_type="country",
                stratum_value="Canada",
                drug_event_count=hyp.canada_reports,
                signal_detected=hyp.canada_signal or False,
            )
        )

    # JADER (do hypothesis result)
    if hyp.jader_reports is not None:
        strata.append(
            StratumSignal(
                source="JADER",
                stratum_type="country",
                stratum_value="JADER",
                drug_event_count=hyp.jader_reports,
                signal_detected=hyp.jader_signal or False,
            )
        )

    return strata


def _build_demographic_summary(
    sex_strata: list[StratumSignal],
    age_strata: list[StratumSignal],
    country_strata: list[StratumSignal],
) -> str:
    """Gera resumo textual comparando PRR entre subgrupos."""
    parts: list[str] = []

    # Sex comparison (FAERS)
    faers_sex = {
        s.stratum_value: s for s in sex_strata if s.source == "FAERS" and not s.insufficient_data
    }
    if "M" in faers_sex and "F" in faers_sex:
        m_prr = faers_sex["M"].prr
        f_prr = faers_sex["F"].prr
        if m_prr > 0 and f_prr > 0:
            ratio = max(m_prr, f_prr) / min(m_prr, f_prr)
            higher = "males" if m_prr > f_prr else "females"
            if ratio >= STRATUM_SEX_NOTABLE_RATIO:
                parts.append(
                    f"Sex: PRR is {ratio:.1f}x higher in {higher} "
                    f"({m_prr:.2f} M vs {f_prr:.2f} F) — notable difference"
                )
            else:
                parts.append(
                    f"Sex: No notable difference between sexes ({m_prr:.2f} M vs {f_prr:.2f} F)"
                )

    # Age comparison
    faers_age = [
        (s.stratum_value, s.prr)
        for s in age_strata
        if s.source == "FAERS" and not s.insufficient_data and s.prr > 0
    ]
    if faers_age:
        max_group, max_prr = max(faers_age, key=lambda x: x[1])
        mean_prr = sum(p for _, p in faers_age) / len(faers_age)
        if mean_prr > 0:
            ratio = max_prr / mean_prr
            if ratio >= STRATUM_AGE_NOTABLE_RATIO:
                parts.append(
                    f"Age: Strongest signal in {max_group} group "
                    f"(PRR {max_prr:.2f}, {ratio:.1f}x average)"
                )
            else:
                parts.append(
                    f"Age: Signal relatively consistent across age groups "
                    f"(strongest in {max_group}, PRR {max_prr:.2f})"
                )

    # Country comparison
    detecting = [s for s in country_strata if s.signal_detected]
    total = len(country_strata)
    if total > 1:
        if len(detecting) == total:
            sources = ", ".join(s.stratum_value for s in detecting)
            parts.append(f"Cross-country: Signal confirmed across all databases ({sources})")
        elif detecting:
            confirmed = ", ".join(s.stratum_value for s in detecting)
            not_confirmed = ", ".join(
                s.stratum_value for s in country_strata if not s.signal_detected
            )
            parts.append(
                f"Cross-country: Signal confirmed in {confirmed} but NOT in {not_confirmed}"
            )
        else:
            parts.append("Cross-country: Signal not confirmed in any database")

    if not parts:
        parts.append("Insufficient data for demographic stratification")

    return "\n".join(f"- {p}" for p in parts)
