"""Testes para drugbank/models.py."""

from __future__ import annotations

from hypokrates.drugbank.models import DrugBankInfo, DrugEnzyme, DrugInteraction, DrugTarget


class TestDrugBankModels:
    """Testes de construção dos models."""

    def test_drug_target_defaults(self) -> None:
        target = DrugTarget(name="GABRA1")
        assert target.name == "GABRA1"
        assert target.gene_name == ""
        assert target.actions == []
        assert target.organism == "Humans"

    def test_drug_target_full(self) -> None:
        target = DrugTarget(
            name="Gamma-aminobutyric acid receptor",
            gene_name="GABRA1",
            actions=["potentiator"],
            organism="Humans",
        )
        assert target.gene_name == "GABRA1"
        assert target.actions == ["potentiator"]

    def test_drug_enzyme_defaults(self) -> None:
        enzyme = DrugEnzyme(name="CYP2B6")
        assert enzyme.name == "CYP2B6"
        assert enzyme.gene_name == ""

    def test_drug_enzyme_full(self) -> None:
        enzyme = DrugEnzyme(name="Cytochrome P450 2B6", gene_name="CYP2B6")
        assert enzyme.gene_name == "CYP2B6"

    def test_drug_interaction_defaults(self) -> None:
        interaction = DrugInteraction(partner_id="DB00813", partner_name="Fentanyl")
        assert interaction.description == ""

    def test_drug_interaction_full(self) -> None:
        interaction = DrugInteraction(
            partner_id="DB00813",
            partner_name="Fentanyl",
            description="CNS depression",
        )
        assert interaction.description == "CNS depression"

    def test_drugbank_info_defaults(self) -> None:
        info = DrugBankInfo(drugbank_id="DB00818", name="Propofol")
        assert info.description == ""
        assert info.mechanism_of_action == ""
        assert info.categories == []
        assert info.targets == []
        assert info.enzymes == []
        assert info.interactions == []

    def test_drugbank_info_full(self) -> None:
        info = DrugBankInfo(
            drugbank_id="DB00818",
            name="Propofol",
            description="IV anesthetic",
            mechanism_of_action="GABA-A potentiator",
            pharmacodynamics="Rapid onset",
            categories=["Anesthetics"],
            synonyms=["Diprivan"],
            targets=[DrugTarget(name="GABRA1")],
            enzymes=[DrugEnzyme(name="CYP2B6", gene_name="CYP2B6")],
            interactions=[DrugInteraction(partner_id="DB00813", partner_name="Fentanyl")],
        )
        assert len(info.targets) == 1
        assert len(info.enzymes) == 1
        assert len(info.interactions) == 1
        assert info.synonyms == ["Diprivan"]
