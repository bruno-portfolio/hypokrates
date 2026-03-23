"""Constantes do módulo scan."""

from __future__ import annotations

from hypokrates.cross.models import HypothesisClassification

DEFAULT_TOP_N = 20
DEFAULT_CONCURRENCY = 5
OVERFETCH_MULTIPLIER: int = 3  # busca N*3 eventos por count, retorna top N por score

CLASSIFICATION_WEIGHTS: dict[HypothesisClassification, float] = {
    HypothesisClassification.NOVEL_HYPOTHESIS: 10.0,
    HypothesisClassification.EMERGING_SIGNAL: 5.0,
    HypothesisClassification.KNOWN_ASSOCIATION: 1.0,
    HypothesisClassification.NO_SIGNAL: 0.0,
    HypothesisClassification.PROTECTIVE_SIGNAL: 3.0,
}

LABEL_NOT_IN_MULTIPLIER: float = 1.5
LABEL_IN_MULTIPLIER: float = 0.5
INDICATION_MULTIPLIER: float = 0.3
CO_ADMIN_MULTIPLIER: float = 0.3  # penalty para items com co-admin confounding

# ---------------------------------------------------------------------------
# Direction analysis — compara PRR ALL/SUSPECT vs PS-only
# ---------------------------------------------------------------------------
DIRECTION_STRENGTHENS_THRESHOLD: float = 1.2  # PS PRR > 1.2x base = fortalece sinal
DIRECTION_WEAKENS_THRESHOLD: float = 0.8  # PS PRR < 0.8x base = enfraquece sinal

# ---------------------------------------------------------------------------
# Termos MedDRA operacionais/regulatórios — NÃO representam toxicidade biológica.
# Descrevem problemas de processo, uso ou reporting, não efeitos adversos reais.
# Filtrados por padrão no scan para evitar poluição dos resultados.
# ---------------------------------------------------------------------------
OPERATIONAL_MEDDRA_TERMS: frozenset[str] = frozenset(
    {
        # Uso / indicação
        "OFF LABEL USE",
        "PRODUCT USE IN UNAPPROVED INDICATION",
        "DRUG USE FOR UNKNOWN INDICATION",
        "INTENTIONAL PRODUCT USE ISSUE",
        "INTENTIONAL PRODUCT MISUSE",
        "PRODUCT USE ISSUE",
        "DRUG INEFFECTIVE",
        "DRUG INEFFECTIVE FOR UNAPPROVED INDICATION",
        "THERAPEUTIC RESPONSE UNEXPECTED",
        "NO ADVERSE EVENT",
        # Erros de medicação / dosagem
        "INCORRECT DOSE ADMINISTERED",
        "INCORRECT DOSE ADMINISTERED BY DEVICE",
        "EXTRA DOSE ADMINISTERED",
        "ACCIDENTAL UNDERDOSE",
        "ACCIDENTAL OVERDOSE",
        "WRONG DRUG ADMINISTERED",
        "WRONG TECHNIQUE IN PRODUCT USAGE PROCESS",
        "PRODUCT DOSE OMISSION ISSUE",
        "PRODUCT DOSE OMISSION",
        "PRODUCT DOSE OMISSION IN ERROR",
        "DRUG DOSE OMISSION",
        "DRUG DOSE OMISSION BY DEVICE",
        "INTENTIONAL DOSE OMISSION",
        "LABELLED DRUG-DRUG INTERACTION MEDICATION ERROR",
        "MEDICATION ERROR",
        "CONTRAINDICATED PRODUCT ADMINISTERED",
        "INAPPROPRIATE SCHEDULE OF PRODUCT ADMINISTRATION",
        # Qualidade do produto / supply chain
        "PRODUCT QUALITY ISSUE",
        "PRODUCT ADHESION ISSUE",
        "PRODUCT PACKAGING ISSUE",
        "PRODUCT PACKAGING CONFUSION",
        "PRODUCT TAMPERING",
        "PRODUCT COUNTERFEIT",
        "PRODUCT SUBSTITUTION ISSUE",
        # Genéricos demais (sem valor farmacológico)
        "DEATH",
        "CONDITION AGGRAVATED",
        "UNEVALUABLE EVENT",
        "DRUG INTERACTION",
        "TOXICITY TO VARIOUS AGENTS",
        "ADVERSE DRUG REACTION",
        "TREATMENT FAILURE",
        "DRUG INTOLERANCE",
        "GENERAL PHYSICAL HEALTH DETERIORATION",
        "PAIN",  # discutível — pode ter valor em contextos específicos
        "FALL",  # discutível — pode ter valor em contextos específicos (ex: sedativos)
        "MALAISE",
        # Exposição (confounding / não é efeito adverso)
        "EXPOSURE DURING PREGNANCY",
        "MATERNAL EXPOSURE DURING PREGNANCY",
        "MATERNAL EXPOSURE DURING DELIVERY",
        "FOETAL EXPOSURE DURING PREGNANCY",
        "ACCIDENTAL EXPOSURE TO PRODUCT",
    }
)

# ---------------------------------------------------------------------------
# Limiar de volume anômalo — acima desse nº de reports (cell 'a' na tabela
# de contingência), o par droga-evento recebe flag de potencial artefato de
# reporting (ex: submissão em lote, litigation-driven, confounding reverso).
# ---------------------------------------------------------------------------
VOLUME_ANOMALY_THRESHOLD: int = 2000

SCAN_METHODOLOGY = (
    "Automated scan of top FAERS adverse events for a drug. "
    "Fetches 3x more events than requested, runs hypothesis() on all, "
    "then returns the top N ranked by score (not raw count). "
    "Scoring combines classification weight x signal strength "
    "(average of PRR and ROR lower CI bounds). "
    "Operational/regulatory MedDRA terms are filtered by default. "
    "Items with >2000 FAERS reports are flagged as potential reporting artifacts."
)

# ---------------------------------------------------------------------------
# compare_class — comparação intra-classe automatizada
# ---------------------------------------------------------------------------
DEFAULT_CLASS_TOP_N: int = 30
DEFAULT_CLASS_CONCURRENCY: int = 5
CLASS_EFFECT_THRESHOLD: float = 0.75  # >=75% das drogas com sinal = class effect
OUTLIER_FACTOR: float = 3.0  # PRR > 3x mediana = outlier

PRR_DISCLAIMER = (
    "PRR (Proportional Reporting Ratio) measures disproportionality of reporting, "
    "NOT absolute risk. A PRR of 10 means 10x more reports than background, "
    "but if the absolute risk is 0.001%, 10x = 0.01% — clinically insignificant. "
    "Always consult meta-analyses and clinical guidelines for risk assessment."
)
