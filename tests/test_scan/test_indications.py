"""Testes para scan/indications.py — filtro de termos de indicacao."""

from __future__ import annotations

from hypokrates.scan.indications import (
    INDICATION_TERMS,
    IndicationCheck,
    check_drug_indication,
    is_indication_term,
)


class TestIsIndicationTerm:
    """Testes para is_indication_term()."""

    def test_known_indication(self) -> None:
        assert is_indication_term("SYSTEMIC LUPUS ERYTHEMATOSUS")

    def test_case_insensitive(self) -> None:
        assert is_indication_term("systemic lupus erythematosus")

    def test_not_indication(self) -> None:
        assert not is_indication_term("BRADYCARDIA")

    def test_indication_set_not_empty(self) -> None:
        assert len(INDICATION_TERMS) > 50

    def test_whitespace_stripped(self) -> None:
        assert is_indication_term("  RHEUMATOID ARTHRITIS  ")

    def test_oncology_indications(self) -> None:
        assert is_indication_term("MULTIPLE MYELOMA")
        assert is_indication_term("LYMPHOMA")
        assert is_indication_term("DISEASE PROGRESSION")

    def test_transplant_indications(self) -> None:
        assert is_indication_term("GRAFT VERSUS HOST DISEASE")
        assert is_indication_term("TRANSPLANT REJECTION")

    def test_autoimmune_indications(self) -> None:
        assert is_indication_term("RHEUMATOID ARTHRITIS")
        assert is_indication_term("CROHN'S DISEASE")
        assert is_indication_term("MULTIPLE SCLEROSIS")

    def test_adrenal_insufficiency_is_indication(self) -> None:
        """ADRENAL INSUFFICIENCY pode ser indicacao E efeito adverso."""
        assert is_indication_term("ADRENAL INSUFFICIENCY")

    def test_unknown_term_not_indication(self) -> None:
        assert not is_indication_term("HEPATOTOXICITY")
        assert not is_indication_term("RHABDOMYOLYSIS")
        assert not is_indication_term("QT PROLONGATION")


class TestCheckDrugIndication:
    """Testes para check_drug_indication() — drug-specific indication detection."""

    def test_generic_term_detected(self) -> None:
        result = check_drug_indication("any_drug", "RHEUMATOID ARTHRITIS")
        assert isinstance(result, IndicationCheck)
        assert result.is_indication is True
        assert result.source == "generic_term"

    def test_not_indication_without_label(self) -> None:
        result = check_drug_indication("propofol", "BRADYCARDIA")
        assert result.is_indication is False
        assert result.source == ""

    def test_drug_specific_from_label(self) -> None:
        indications_text = (
            "SUGAMMADEX is indicated for reversal of neuromuscular blockade "
            "induced by rocuronium or vecuronium."
        )
        result = check_drug_indication(
            "sugammadex", "NEUROMUSCULAR BLOCKADE", indications_text=indications_text
        )
        assert result.is_indication is True
        assert result.source == "dailymed_label"

    def test_drug_specific_no_match(self) -> None:
        indications_text = "Indicated for reversal of neuromuscular blockade."
        result = check_drug_indication(
            "sugammadex", "ANAPHYLAXIS", indications_text=indications_text
        )
        assert result.is_indication is False

    def test_generic_takes_priority_over_label(self) -> None:
        indications_text = "Indicated for asthma management."
        result = check_drug_indication("budesonide", "ASTHMA", indications_text=indications_text)
        assert result.is_indication is True
        assert result.source == "generic_term"

    def test_empty_indications_text(self) -> None:
        result = check_drug_indication("propofol", "DELIRIUM", indications_text="")
        assert result.is_indication is False
