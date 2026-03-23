"""Termos MedDRA que representam indicacoes, nao eventos adversos.

Estes termos aparecem no FAERS como 'reactions' mas na verdade descrevem
a condicao de base do paciente (confounding por indicacao).
"""

from __future__ import annotations

from pydantic import BaseModel


class IndicationCheck(BaseModel):
    """Resultado da verificação de indicação (genérica ou drug-specific)."""

    is_indication: bool = False
    source: str = ""


# Termos que sao indicacoes/condicoes de base, nao efeitos adversos
# Quando aparecem com PRR alto, refletem o perfil de uso da droga,
# nao toxicidade
INDICATION_TERMS: frozenset[str] = frozenset(
    {
        # Autoimmune / Rheumatic
        "SYSTEMIC LUPUS ERYTHEMATOSUS",
        "RHEUMATOID ARTHRITIS",
        "POLYMYALGIA RHEUMATICA",
        "GIANT CELL ARTERITIS",
        "VASCULITIS",
        "SARCOIDOSIS",
        "DERMATOMYOSITIS",
        "POLYMYOSITIS",
        "MYASTHENIA GRAVIS",
        "SJOGREN'S SYNDROME",
        "SCLERODERMA",
        "SYSTEMIC SCLEROSIS",
        "MIXED CONNECTIVE TISSUE DISEASE",
        "ANTIPHOSPHOLIPID SYNDROME",
        # Respiratory
        "ASTHMA",
        "CHRONIC OBSTRUCTIVE PULMONARY DISEASE",
        "COPD",
        "INTERSTITIAL LUNG DISEASE",
        "PULMONARY FIBROSIS",
        # Oncology
        "PLASMA CELL MYELOMA",
        "MULTIPLE MYELOMA",
        "LYMPHOMA",
        "NON-HODGKIN'S LYMPHOMA",
        "LEUKAEMIA",
        "LEUKEMIA",
        "ACUTE LYMPHOCYTIC LEUKAEMIA",
        "CHRONIC LYMPHOCYTIC LEUKAEMIA",
        "MALIGNANT NEOPLASM PROGRESSION",
        "DISEASE PROGRESSION",
        "METASTASES TO BONE",
        "METASTASES TO LIVER",
        "METASTASES TO LUNG",
        "METASTASES TO BRAIN",
        # Transplant
        "GRAFT VERSUS HOST DISEASE",
        "TRANSPLANT REJECTION",
        "ORGAN TRANSPLANT",
        "RENAL TRANSPLANT",
        "LIVER TRANSPLANT",
        # Dermatologic
        "PEMPHIGUS",
        "BULLOUS PEMPHIGOID",
        "PSORIASIS",
        "DERMATITIS",
        "ECZEMA",
        "ATOPIC DERMATITIS",
        # Gastrointestinal
        "CROHN'S DISEASE",
        "ULCERATIVE COLITIS",
        "INFLAMMATORY BOWEL DISEASE",
        # Renal
        "NEPHROTIC SYNDROME",
        "GLOMERULONEPHRITIS",
        "LUPUS NEPHRITIS",
        # Neurologic
        "MULTIPLE SCLEROSIS",
        # Allergic
        "ALLERGIC RHINITIS",
        # Infectious context (not the drug's fault)
        "COVID-19",
        "SARS-COV-2 TEST POSITIVE",
        # Cardiac indications
        "ATRIAL FIBRILLATION",
        "HEART FAILURE",
        "VENTRICULAR TACHYCARDIA",
        # Other common indications
        "ADRENAL INSUFFICIENCY",
        "ADDISON'S DISEASE",
        "CEREBRAL OEDEMA",
        "SPINAL CORD COMPRESSION",
    }
)


def is_indication_term(event: str) -> bool:
    """Verifica se um termo MedDRA e uma indicacao conhecida."""
    return event.upper().strip() in INDICATION_TERMS


def check_drug_indication(
    drug: str,
    event: str,
    *,
    indications_text: str = "",
) -> IndicationCheck:
    """Checa se event é indicação genérica OU indicação específica desta droga."""
    if is_indication_term(event):
        return IndicationCheck(is_indication=True, source="generic_term")
    if indications_text:
        from hypokrates.dailymed.parser import match_event_in_label

        found, _ = match_event_in_label(event, [], indications_text)
        if found:
            return IndicationCheck(is_indication=True, source="dailymed_label")
    return IndicationCheck()
