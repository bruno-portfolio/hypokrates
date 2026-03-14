"""Testes para chembl/models.py."""

from __future__ import annotations

from datetime import UTC, datetime

from hypokrates.chembl.models import (
    ChEMBLMechanism,
    ChEMBLMetabolism,
    ChEMBLTarget,
    MetabolismPathway,
)
from hypokrates.models import MetaInfo


def _meta() -> MetaInfo:
    return MetaInfo(source="test", retrieved_at=datetime.now(UTC))


class TestChEMBLModels:
    """Testes de construção dos models."""

    def test_target_defaults(self) -> None:
        t = ChEMBLTarget(target_chembl_id="CHEMBL1")
        assert t.gene_names == []
        assert t.organism == "Homo sapiens"

    def test_target_full(self) -> None:
        t = ChEMBLTarget(
            target_chembl_id="CHEMBL2093872",
            name="GABA-A receptor",
            gene_names=["GABRA1", "GABRB2"],
        )
        assert len(t.gene_names) == 2

    def test_pathway_defaults(self) -> None:
        p = MetabolismPathway()
        assert p.enzyme_name == ""
        assert p.conversion == ""

    def test_mechanism_defaults(self) -> None:
        m = ChEMBLMechanism(chembl_id="CHEMBL526", meta=_meta())
        assert m.mechanism_of_action == ""
        assert m.targets == []

    def test_mechanism_full(self) -> None:
        m = ChEMBLMechanism(
            chembl_id="CHEMBL526",
            drug_name="PROPOFOL",
            mechanism_of_action="GABA-A modulator",
            action_type="POSITIVE ALLOSTERIC MODULATOR",
            targets=[ChEMBLTarget(target_chembl_id="T1", gene_names=["GABRA1"])],
            max_phase=4,
            meta=_meta(),
        )
        assert m.max_phase == 4
        assert len(m.targets) == 1

    def test_metabolism_defaults(self) -> None:
        m = ChEMBLMetabolism(chembl_id="CHEMBL526", meta=_meta())
        assert m.pathways == []

    def test_metabolism_full(self) -> None:
        m = ChEMBLMetabolism(
            chembl_id="CHEMBL526",
            drug_name="PROPOFOL",
            pathways=[
                MetabolismPathway(
                    substrate_name="Propofol",
                    metabolite_name="Propofol glucuronide",
                    conversion="Glucuronidation",
                )
            ],
            meta=_meta(),
        )
        assert len(m.pathways) == 1
