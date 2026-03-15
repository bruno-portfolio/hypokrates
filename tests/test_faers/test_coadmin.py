"""Testes para co_suspect_profile() — Layer 1 co-admin detection."""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock

import httpx
import respx

from hypokrates.config import configure
from hypokrates.faers.api import co_suspect_profile
from hypokrates.faers.constants import CO_ADMIN_THRESHOLD, DRUG_CHARACTERIZATION_SUSPECT
from tests.helpers import make_raw_drug, make_raw_patient, make_raw_reaction, make_raw_report


def _make_or_report(
    report_id: str,
    *,
    event: str = "ANAPHYLACTIC SHOCK",
    drugs: list[tuple[str, str]] | None = None,
) -> dict[str, Any]:
    """Cria report simulando setting de OR com múltiplos suspects.

    Args:
        report_id: ID do report.
        event: Termo MedDRA.
        drugs: Lista de (nome, role). Default: 5 suspects típicos de OR.
    """
    if drugs is None:
        drugs = [
            ("PROPOFOL", "1"),
            ("ROCURONIUM", "1"),
            ("FENTANYL", "1"),
            ("CEFAZOLIN", "1"),
            ("MIDAZOLAM", "1"),
        ]
    raw_drugs = [make_raw_drug(name=n, role=r) for n, r in drugs]
    patient = make_raw_patient(
        reactions=[make_raw_reaction(term=event)],
        drugs=raw_drugs,
    )
    return make_raw_report(report_id=report_id, patient=patient)


def _make_single_suspect_report(
    report_id: str,
    *,
    event: str = "PROPOFOL INFUSION SYNDROME",
) -> dict[str, Any]:
    """Report com propofol como único suspect."""
    raw_drugs = [
        make_raw_drug(name="PROPOFOL", role="1"),
        make_raw_drug(name="FENTANYL", role="2"),  # concomitant
        make_raw_drug(name="MIDAZOLAM", role="2"),  # concomitant
    ]
    patient = make_raw_patient(
        reactions=[make_raw_reaction(term=event)],
        drugs=raw_drugs,
    )
    return make_raw_report(report_id=report_id, patient=patient)


def _openfda_response(reports: list[dict[str, Any]]) -> dict[str, Any]:
    """Wrap reports em resposta OpenFDA."""
    return {
        "meta": {"results": {"total": len(reports)}},
        "results": reports,
    }


class TestCoSuspectProfileBasic:
    """Cenário OR: múltiplos suspects por report."""

    @respx.mock
    async def test_multiple_suspects_flags_coadmin(self) -> None:
        configure(cache_enabled=False)
        reports = [_make_or_report(f"OR{i:03d}") for i in range(5)]

        # Mock drug field resolution
        respx.get(url__startswith="https://api.fda.gov").mock(
            return_value=httpx.Response(200, json=_openfda_response(reports))
        )

        profile = await co_suspect_profile("propofol", "anaphylactic shock")

        assert profile.drug == "PROPOFOL"
        assert profile.event == "ANAPHYLACTIC SHOCK"
        assert profile.sample_size == 5
        assert profile.median_suspects == 5.0
        assert profile.co_admin_flag is True
        assert profile.max_suspects == 5

    @respx.mock
    async def test_single_suspect_no_flag(self) -> None:
        configure(cache_enabled=False)
        reports = [_make_single_suspect_report(f"SS{i:03d}") for i in range(5)]

        respx.get(url__startswith="https://api.fda.gov").mock(
            return_value=httpx.Response(200, json=_openfda_response(reports))
        )

        profile = await co_suspect_profile("propofol", "propofol infusion syndrome")

        assert profile.median_suspects == 1.0
        assert profile.co_admin_flag is False

    @respx.mock
    async def test_empty_results_returns_default(self) -> None:
        configure(cache_enabled=False)
        respx.get(url__startswith="https://api.fda.gov").mock(
            return_value=httpx.Response(200, json=_openfda_response([]))
        )

        profile = await co_suspect_profile("unknowndrug", "unknownevent")

        assert profile.sample_size == 0
        assert profile.median_suspects == 0.0
        assert profile.co_admin_flag is False
        assert profile.top_co_drugs == []


class TestCoSuspectProfileDrugCounting:
    """Contagem e extração de co-drugs."""

    @respx.mock
    async def test_excludes_index_drug_from_co_drugs(self) -> None:
        configure(cache_enabled=False)
        reports = [_make_or_report(f"EX{i:03d}") for i in range(3)]

        respx.get(url__startswith="https://api.fda.gov").mock(
            return_value=httpx.Response(200, json=_openfda_response(reports))
        )

        profile = await co_suspect_profile("propofol", "anaphylactic shock")

        co_drug_names = [name for name, _ in profile.top_co_drugs]
        assert "PROPOFOL" not in co_drug_names
        assert "ROCURONIUM" in co_drug_names
        assert "FENTANYL" in co_drug_names

    @respx.mock
    async def test_counts_only_suspect_role(self) -> None:
        """Drogas com role!=1 não devem ser contadas como suspects."""
        configure(cache_enabled=False)
        drugs = [
            ("PROPOFOL", "1"),  # suspect
            ("FENTANYL", "2"),  # concomitant — não deve contar
            ("MIDAZOLAM", "3"),  # interacting — não deve contar
        ]
        reports = [_make_or_report(f"RC{i:03d}", drugs=drugs) for i in range(5)]

        respx.get(url__startswith="https://api.fda.gov").mock(
            return_value=httpx.Response(200, json=_openfda_response(reports))
        )

        profile = await co_suspect_profile("propofol", "anaphylactic shock")

        assert profile.median_suspects == 1.0
        assert profile.co_admin_flag is False
        co_drug_names = [name for name, _ in profile.top_co_drugs]
        assert "FENTANYL" not in co_drug_names
        assert "MIDAZOLAM" not in co_drug_names

    @respx.mock
    async def test_top_co_drugs_ordered_by_frequency(self) -> None:
        """Top co-drugs devem ser ordenados por frequência."""
        configure(cache_enabled=False)
        # Rocuronium em todos os 5, fentanyl em 3, cefazolin em 1
        reports = []
        for i in range(5):
            drugs: list[tuple[str, str]] = [("PROPOFOL", "1"), ("ROCURONIUM", "1")]
            if i < 3:
                drugs.append(("FENTANYL", "1"))
            if i < 1:
                drugs.append(("CEFAZOLIN", "1"))
            reports.append(_make_or_report(f"OF{i:03d}", drugs=drugs))

        respx.get(url__startswith="https://api.fda.gov").mock(
            return_value=httpx.Response(200, json=_openfda_response(reports))
        )

        profile = await co_suspect_profile("propofol", "anaphylactic shock")

        assert profile.top_co_drugs[0][0] == "ROCURONIUM"
        assert profile.top_co_drugs[0][1] == 5
        assert profile.top_co_drugs[1][0] == "FENTANYL"
        assert profile.top_co_drugs[1][1] == 3

    @respx.mock
    async def test_mixed_suspect_counts(self) -> None:
        """Reports com quantidades variadas de suspects."""
        configure(cache_enabled=False)
        reports = [
            _make_or_report("MX001", drugs=[("PROPOFOL", "1"), ("ROCURONIUM", "1")]),
            _make_or_report("MX002", drugs=[("PROPOFOL", "1")]),
            _make_or_report(
                "MX003",
                drugs=[
                    ("PROPOFOL", "1"),
                    ("ROCURONIUM", "1"),
                    ("FENTANYL", "1"),
                    ("CEFAZOLIN", "1"),
                    ("MIDAZOLAM", "1"),
                ],
            ),
        ]

        respx.get(url__startswith="https://api.fda.gov").mock(
            return_value=httpx.Response(200, json=_openfda_response(reports))
        )

        profile = await co_suspect_profile("propofol", "anaphylactic shock")

        assert profile.sample_size == 3
        # suspects: [2, 1, 5] → median=2
        assert profile.median_suspects == 2.0
        assert profile.mean_suspects == round((2 + 1 + 5) / 3, 2)
        assert profile.max_suspects == 5


class TestCoSuspectProfileIntegration:
    """Testes de integração: reuso de client, suspect_only."""

    @respx.mock
    async def test_suspect_only_adds_filter(self) -> None:
        """Query deve incluir drugcharacterization:1 quando suspect_only=True."""
        configure(cache_enabled=False)
        reports = [_make_or_report("SO001")]

        route = respx.get(url__startswith="https://api.fda.gov").mock(
            return_value=httpx.Response(200, json=_openfda_response(reports))
        )

        await co_suspect_profile("propofol", "anaphylactic shock", suspect_only=True)

        # Verificar que a query contém o filtro de suspect
        call_url = str(route.calls[0].request.url)
        assert (
            f"drugcharacterization%3A{DRUG_CHARACTERIZATION_SUSPECT}" in call_url
            or f"drugcharacterization:{DRUG_CHARACTERIZATION_SUSPECT}" in call_url
        )

    @respx.mock
    async def test_reuses_client_and_drug_search(self) -> None:
        """Quando _client e _drug_search são fornecidos, não cria novo client."""
        configure(cache_enabled=False)
        reports = [_make_or_report("RC001")]

        mock_client = AsyncMock()
        mock_client.fetch = AsyncMock(return_value=_openfda_response(reports))

        profile = await co_suspect_profile(
            "propofol",
            "anaphylactic shock",
            _client=mock_client,
            _drug_search='patient.drug.openfda.generic_name.exact:"PROPOFOL"',
        )

        mock_client.fetch.assert_called_once()
        assert profile.sample_size == 1
        assert profile.co_admin_flag is True

    @respx.mock
    async def test_threshold_boundary(self) -> None:
        """Exatamente no threshold não deve flaggar (> não >=)."""
        configure(cache_enabled=False)
        # 3 suspects por report = threshold = 3.0 → NÃO flag (> 3.0)
        drugs = [("PROPOFOL", "1"), ("ROCURONIUM", "1"), ("FENTANYL", "1")]
        reports = [_make_or_report(f"TB{i:03d}", drugs=drugs) for i in range(5)]

        respx.get(url__startswith="https://api.fda.gov").mock(
            return_value=httpx.Response(200, json=_openfda_response(reports))
        )

        profile = await co_suspect_profile("propofol", "anaphylactic shock")

        assert profile.median_suspects == CO_ADMIN_THRESHOLD
        assert profile.co_admin_flag is False  # > threshold, não >=
