"""Golden data para suíte sentinela — definições dos casos de referência.

Cada caso define:
- drug + event
- cenário (o que estamos testando)
- expectativas: classificação, PRR range, in_label, volume_flag, etc.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from hypokrates.cross.models import HypothesisClassification


@dataclass(frozen=True)
class SentinelCase:
    """Caso sentinela com expectativas de resultado."""

    drug: str
    event: str
    scenario: str
    # Expectativas de signal
    signal_detected: bool = True
    prr_min: float = 1.0
    prr_max: float = 1000.0
    # Expectativas de classification
    classification: HypothesisClassification | None = None
    allowed_classifications: tuple[HypothesisClassification, ...] = ()
    # Expectativas de label
    in_label: bool | None = None
    # Expectativas de scan
    volume_flag: bool = False
    coadmin_flag: bool = False
    min_reports: int = 3
    # Contexto
    description: str = ""


@dataclass(frozen=True)
class BrandCase:
    """Caso de normalização brand→generic."""

    brand: str
    expected_generic: str
    description: str = ""


@dataclass(frozen=True)
class MedDRAGroupCase:
    """Caso de agrupamento MedDRA."""

    terms: list[str] = field(default_factory=list)
    expected_canonical: str = ""
    description: str = ""


@dataclass(frozen=True)
class FailureCase:
    """Caso de falha graciosa."""

    drug: str
    event: str
    scenario: str
    should_crash: bool = False
    expected_behavior: str = ""


# ---------------------------------------------------------------------------
# 1. Sinais reais / controles positivos / confounding / artefatos
# ---------------------------------------------------------------------------

SIGNAL_CASES: list[SentinelCase] = [
    # === Sinal real ===
    SentinelCase(
        drug="propofol",
        event="ANAPHYLACTIC SHOCK",
        scenario="real_signal",
        signal_detected=True,
        prr_min=1.5,
        classification=HypothesisClassification.KNOWN_ASSOCIATION,
        in_label=True,
        description="Propofol + anaphylactic shock: sinal real, in_label, KNOWN.",
    ),
    # === Controle positivo forte ===
    SentinelCase(
        drug="amiodarone",
        event="PULMONARY TOXICITY",
        scenario="strong_positive_control",
        signal_detected=True,
        prr_min=5.0,
        classification=HypothesisClassification.KNOWN_ASSOCIATION,
        in_label=True,
        description="Amiodarone + pulmonary toxicity: controle positivo textbook.",
    ),
    # === Confounding por co-admin ===
    SentinelCase(
        drug="ondansetron",
        event="FEBRILE NEUTROPENIA",
        scenario="coadmin_confounding",
        signal_detected=True,
        coadmin_flag=True,
        description="Ondansetron + febrile neutropenia: sinal de quimio, não do antiemético.",
    ),
    # === Artefato de reporting ===
    SentinelCase(
        drug="cetirizine",
        event="GLOSSODYNIA",
        scenario="reporting_artifact",
        signal_detected=True,
        volume_flag=True,
        description="Cetirizine + glossodynia: volume anômalo, provável artefato.",
    ),
    # === Novel/Emerging (poucos papers) ===
    SentinelCase(
        drug="etomidate",
        event="ANHEDONIA",
        scenario="novel_or_emerging",
        signal_detected=True,
        prr_min=5.0,
        allowed_classifications=(
            HypothesisClassification.NOVEL_HYPOTHESIS,
            HypothesisClassification.EMERGING_SIGNAL,
        ),
        in_label=False,
        description="Etomidate + anhedonia: sinal robusto, poucos papers, não na bula.",
    ),
    # === Known forte ===
    SentinelCase(
        drug="metformin",
        event="LACTIC ACIDOSIS",
        scenario="known_strong",
        signal_detected=True,
        prr_min=2.0,
        classification=HypothesisClassification.KNOWN_ASSOCIATION,
        in_label=True,
        description="Metformin + lactic acidosis: known association clássica.",
    ),
    # === Sinal fraco / negativo ===
    SentinelCase(
        drug="acetaminophen",
        event="HAIR LOSS",
        scenario="weak_or_no_signal",
        signal_detected=False,
        allowed_classifications=(
            HypothesisClassification.NO_SIGNAL,
            HypothesisClassification.EMERGING_SIGNAL,
        ),
        description="Acetaminophen + hair loss: relação improvável, sem sinal forte.",
    ),
    # === Controle negativo limpo ===
    SentinelCase(
        drug="ketamine",
        event="ANHEDONIA",
        scenario="negative_control",
        signal_detected=False,
        prr_max=2.0,
        allowed_classifications=(
            HypothesisClassification.NO_SIGNAL,
            HypothesisClassification.EMERGING_SIGNAL,
        ),
        description="Ketamine + anhedonia: controle negativo (ketamine é antidepressivo).",
    ),
]

# ---------------------------------------------------------------------------
# 2. Label validation (DailyMed SPL selection)
# ---------------------------------------------------------------------------

LABEL_CASES: list[SentinelCase] = [
    SentinelCase(
        drug="lidocaine",
        event="CARDIAC ARREST",
        scenario="label_correct_spl",
        signal_detected=True,
        in_label=True,
        description="Lidocaine label_events: deve selecionar SPL humano (injection, não patch).",
    ),
    SentinelCase(
        drug="ketamine",
        event="HALLUCINATION",
        scenario="label_human_not_vet",
        signal_detected=True,
        in_label=True,
        description="Ketamine label_events: humano, não veterinário.",
    ),
]

# ---------------------------------------------------------------------------
# 3. Brand → generic normalization
# ---------------------------------------------------------------------------

BRAND_CASES: list[BrandCase] = [
    BrandCase(
        brand="Diprivan",
        expected_generic="propofol",
        description="Diprivan → propofol (anestésico IV).",
    ),
    BrandCase(
        brand="Ozempic",
        expected_generic="semaglutide",
        description="Ozempic → semaglutide (GLP-1).",
    ),
    BrandCase(
        brand="Tylenol",
        expected_generic="acetaminophen",
        description="Tylenol → acetaminophen (analgésico).",
    ),
]

# ---------------------------------------------------------------------------
# 4. MedDRA grouping
# ---------------------------------------------------------------------------

MEDDRA_CASES: list[MedDRAGroupCase] = [
    MedDRAGroupCase(
        terms=["QT PROLONGATION", "ELECTROCARDIOGRAM QT PROLONGED", "LONG QT SYNDROME"],
        expected_canonical="QT PROLONGATION",
        description="Termos de QT agrupam sob QT PROLONGATION.",
    ),
    MedDRAGroupCase(
        terms=["ANAPHYLACTIC SHOCK", "ANAPHYLACTIC REACTION", "ANAPHYLAXIS"],
        expected_canonical="ANAPHYLAXIS",
        description="Termos anafilaxia agrupam sob ANAPHYLAXIS.",
    ),
    MedDRAGroupCase(
        terms=["SINUS BRADYCARDIA", "HEART RATE DECREASED", "BRADYCARDIA"],
        expected_canonical="BRADYCARDIA",
        description="Termos bradicardia agrupam sob BRADYCARDIA.",
    ),
]

# ---------------------------------------------------------------------------
# 5. Falha graciosa
# ---------------------------------------------------------------------------

FAILURE_CASES: list[FailureCase] = [
    FailureCase(
        drug="xyznonexistent123",
        event="NAUSEA",
        scenario="nonexistent_drug",
        should_crash=False,
        expected_behavior="Retorna resultado vazio ou no_signal, sem crash.",
    ),
    FailureCase(
        drug="propofol",
        event="XYZFAKEEVENT999",
        scenario="nonexistent_event",
        should_crash=False,
        expected_behavior="Retorna no_signal, sem crash.",
    ),
    FailureCase(
        drug="propofol",
        event="NAUSEA",
        scenario="drugbank_absent",
        should_crash=False,
        expected_behavior="DrugBank ausente → degrada gracefully, campos None.",
    ),
    FailureCase(
        drug="propofol",
        event="NAUSEA",
        scenario="dailymed_no_spl",
        should_crash=False,
        expected_behavior="DailyMed sem SPL → in_label=None, sem crash.",
    ),
    FailureCase(
        drug="propofol",
        event="NAUSEA",
        scenario="bulk_store_empty",
        should_crash=False,
        expected_behavior="Bulk store vazio → fallback para API, sem crash.",
    ),
]

# ---------------------------------------------------------------------------
# 6. Drogas ruidosas (scan completo)
# ---------------------------------------------------------------------------

NOISY_DRUGS: list[str] = [
    "prednisone",
    "dexamethasone",
    "atorvastatin",
    "ibuprofen",
    "omeprazole",
]

# ---------------------------------------------------------------------------
# 7. Consistência cross-tool
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class ConsistencyCase:
    """Caso de consistência entre tools."""

    drug: str
    event: str
    description: str = ""


CONSISTENCY_CASES: list[ConsistencyCase] = [
    ConsistencyCase(
        drug="propofol",
        event="ANAPHYLAXIS",
        description="signal + hypothesis + check_label + drug_safety_score devem concordar.",
    ),
    ConsistencyCase(
        drug="amiodarone",
        event="PULMONARY FIBROSIS",
        description="Todas as tools devem reportar sinal forte e in_label.",
    ),
    ConsistencyCase(
        drug="metformin",
        event="LACTIC ACIDOSIS",
        description="Known association clássica — concordância obrigatória.",
    ),
]
