"""Testes para pharmgkb/api.py — mock HTTP com respx."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
import respx
from httpx import Response

from hypokrates.pharmgkb.api import pgx_annotations, pgx_drug_info, pgx_guidelines
from hypokrates.pharmgkb.constants import PHARMGKB_BASE_URL

GOLDEN_DIR = Path(__file__).parent.parent / "golden_data" / "pharmgkb"


def _load(name: str) -> dict:
    return json.loads((GOLDEN_DIR / name).read_text())


@pytest.fixture(autouse=True)
def _mock_pharmgkb(respx_mock: respx.MockRouter) -> None:
    """Mock PharmGKB API endpoints."""
    base = PHARMGKB_BASE_URL

    respx_mock.get(f"{base}/chemical", params__contains={"name": "propofol"}).mock(
        return_value=Response(200, json=_load("chemical_propofol.json"))
    )
    respx_mock.get(f"{base}/chemical", params__contains={"name": "warfarin"}).mock(
        return_value=Response(200, json={"data": [{"id": "PA451906"}], "status": "success"})
    )
    respx_mock.get(
        f"{base}/clinicalAnnotation",
        params__contains={"relatedChemicals.name": "propofol"},
    ).mock(return_value=Response(200, json=_load("annotations_propofol.json")))
    respx_mock.get(
        f"{base}/clinicalAnnotation",
        params__contains={"relatedChemicals.name": "warfarin"},
    ).mock(return_value=Response(200, json=_load("annotations_warfarin.json")))
    respx_mock.get(
        f"{base}/guidelineAnnotation",
        params__contains={"relatedChemicals.name": "propofol"},
    ).mock(return_value=Response(200, json={"data": [], "status": "success"}))
    respx_mock.get(
        f"{base}/guidelineAnnotation",
        params__contains={"relatedChemicals.name": "warfarin"},
    ).mock(return_value=Response(200, json=_load("guidelines_warfarin.json")))


class TestPharmGKBAPI:
    """Testes da API pública async (mock HTTP)."""

    async def test_pgx_annotations_propofol(self) -> None:
        anns = await pgx_annotations("propofol", use_cache=False)
        assert len(anns) >= 2
        genes = [a.gene_symbol for a in anns]
        assert "CYP2B6" in genes

    async def test_pgx_annotations_warfarin(self) -> None:
        anns = await pgx_annotations("warfarin", use_cache=False)
        assert len(anns) >= 2
        # VKORC1 and CYP2C9 should be 1A
        vkorc1 = [a for a in anns if a.gene_symbol == "VKORC1"]
        assert len(vkorc1) == 1
        assert vkorc1[0].level_of_evidence == "1A"

    async def test_pgx_annotations_min_level(self) -> None:
        all_anns = await pgx_annotations("propofol", min_level="4", use_cache=False)
        strict_anns = await pgx_annotations("propofol", min_level="2B", use_cache=False)
        assert len(all_anns) >= len(strict_anns)

    async def test_pgx_guidelines_warfarin(self) -> None:
        guides = await pgx_guidelines("warfarin", use_cache=False)
        assert len(guides) >= 2
        sources = [g.source for g in guides]
        assert "CPIC" in sources

    async def test_pgx_guidelines_propofol_empty(self) -> None:
        guides = await pgx_guidelines("propofol", use_cache=False)
        assert guides == []

    async def test_pgx_drug_info_propofol(self) -> None:
        result = await pgx_drug_info("propofol", use_cache=False)
        assert result.drug_name == "propofol"
        assert result.pharmgkb_id == "PA450688"
        assert len(result.annotations) >= 2
        assert result.meta.source == "PharmGKB"

    async def test_pgx_drug_info_warfarin(self) -> None:
        result = await pgx_drug_info("warfarin", use_cache=False)
        assert result.drug_name == "warfarin"
        assert len(result.annotations) >= 2
        assert len(result.guidelines) >= 2
