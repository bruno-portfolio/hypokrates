"""Testes para scan/indications.py — filtro de termos de indicacao."""

from __future__ import annotations

from hypokrates.scan.indications import INDICATION_TERMS, is_indication_term


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
