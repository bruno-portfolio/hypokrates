"""Benchmark registry — casos curados de drug-event pairs com comportamento esperado.

Baseado na sessão de validação de 2026-03-14 e testes subsequentes.
Usado para regressão: cada sprint roda contra este registro e verifica
que os gold standards continuam detectados e os negativos continuam limpos.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


class BenchmarkCategory(StrEnum):
    """Categoria do caso de benchmark."""

    KNOWN_SIGNAL = "known_signal"
    KNOWN_NOISE = "known_noise"
    CONFOUNDING = "confounding"
    EMERGING = "emerging"
    PROBLEMATIC = "problematic"
    ONTOLOGY = "ontology"
    REPURPOSING = "repurposing"


class ExpectedDirection(StrEnum):
    """Direção esperada do sinal."""

    SIGNAL = "signal"
    NO_SIGNAL = "no_signal"
    CONFOUNDED = "confounded"


class ExpectedStrength(StrEnum):
    """Força esperada do sinal."""

    STRONG = "strong"
    MODERATE = "moderate"
    WEAK = "weak"
    NONE = "none"


@dataclass
class BenchmarkCase:
    """Um caso de benchmark curado."""

    drug: str
    event: str
    category: BenchmarkCategory
    expected_direction: ExpectedDirection
    expected_strength: ExpectedStrength
    notes: str
    strata_expectation: str | None = None
    confounding_expectation: str | None = None


# --- KNOWN_SIGNAL (gold standards indiscutiveis) ---

_KNOWN_SIGNALS = [
    BenchmarkCase(
        "rocuronium",
        "anaphylactic shock",
        BenchmarkCategory.KNOWN_SIGNAL,
        ExpectedDirection.SIGNAL,
        ExpectedStrength.STRONG,
        "BNM #1 causa de anafilaxia perioperatoria. 257 papers, OT logLR=1614",
        strata_expectation="PRR mulheres > PRR homens (literatura confirma 3x)",
    ),
    BenchmarkCase(
        "clozapine",
        "agranulocytosis",
        BenchmarkCategory.KNOWN_SIGNAL,
        ExpectedDirection.SIGNAL,
        ExpectedStrength.STRONG,
        "Gold standard absoluto. Monitoring obrigatorio (REMS). Incidencia ~1%",
    ),
    BenchmarkCase(
        "amiodarone",
        "pulmonary toxicity",
        BenchmarkCategory.KNOWN_SIGNAL,
        ExpectedDirection.SIGNAL,
        ExpectedStrength.STRONG,
        "Dose-dependente, incidencia 2-17%. Bem estabelecido desde decadas",
    ),
    BenchmarkCase(
        "carbamazepine",
        "toxic epidermal necrolysis",
        BenchmarkCategory.KNOWN_SIGNAL,
        ExpectedDirection.SIGNAL,
        ExpectedStrength.STRONG,
        "HLA-B*1502 associado. Guidelines CPIC. Farmacogenomica validada",
    ),
    BenchmarkCase(
        "heparin",
        "thrombocytopenia",
        BenchmarkCategory.KNOWN_SIGNAL,
        ExpectedDirection.SIGNAL,
        ExpectedStrength.STRONG,
        "HIT tipo II. Mecanismo imunologico bem estabelecido",
    ),
    BenchmarkCase(
        "sugammadex",
        "anaphylactic shock",
        BenchmarkCategory.KNOWN_SIGNAL,
        ExpectedDirection.SIGNAL,
        ExpectedStrength.STRONG,
        "Bula FDA cita 0.3%. Sinal limpissimo (median 1.0 suspect/report)",
        strata_expectation="PRR similar entre sexos (sem variacao na literatura)",
    ),
]

# --- CONFOUNDING (co-admin, indication, notoriety) ---

_CONFOUNDING = [
    BenchmarkCase(
        "propofol",
        "anaphylactic shock",
        BenchmarkCategory.CONFOUNDING,
        ExpectedDirection.SIGNAL,
        ExpectedStrength.MODERATE,
        "Sinal real mas inflado pelo cocktail anestesico. Median 3.0 suspects/report",
        confounding_expectation="PRR deve cair com RGPS ajustando co-admin",
    ),
    BenchmarkCase(
        "ketamine",
        "anaphylactic shock",
        BenchmarkCategory.CONFOUNDING,
        ExpectedDirection.CONFOUNDED,
        ExpectedStrength.WEAK,
        "Median 6.0 suspects/report. Quase certeza artefato do cocktail",
        confounding_expectation="RGPS deve eliminar ou reduzir muito o sinal",
    ),
    BenchmarkCase(
        "ondansetron",
        "febrile neutropenia",
        BenchmarkCategory.CONFOUNDING,
        ExpectedDirection.CONFOUNDED,
        ExpectedStrength.WEAK,
        "Confounding por co-admin com quimioterapia",
    ),
    BenchmarkCase(
        "isotretinoin",
        "depression",
        BenchmarkCategory.CONFOUNDING,
        ExpectedDirection.SIGNAL,
        ExpectedStrength.MODERATE,
        "Controverso. Confounding por indicacao (adolescentes com acne severa) "
        "+ vies de notoriedade",
        confounding_expectation="RGPS com age adjustment pode reduzir sinal",
    ),
]

# --- EMERGING (achados interessantes, nao gold-standard) ---

_EMERGING = [
    BenchmarkCase(
        "etomidate",
        "anhedonia",
        BenchmarkCategory.EMERGING,
        ExpectedDirection.SIGNAL,
        ExpectedStrength.MODERATE,
        "Achado da validacao hypokrates. PRR=41.19, mecanismo plausivel "
        "(supressao adrenal). Nao gold-standard — precisa de validacao externa",
    ),
]

# --- PROBLEMATIC (reporting anomalies) ---

_PROBLEMATIC = [
    BenchmarkCase(
        "cetirizine",
        "glossodynia",
        BenchmarkCategory.PROBLEMATIC,
        ExpectedDirection.SIGNAL,
        ExpectedStrength.WEAK,
        "Volume anomalo (7743+ reports). Provavelmente artefato de stimulated reporting",
    ),
]

# --- KNOWN_NOISE (true negatives) ---

_KNOWN_NOISE = [
    BenchmarkCase(
        "cisatracurium",
        "anhedonia",
        BenchmarkCategory.KNOWN_NOISE,
        ExpectedDirection.NO_SIGNAL,
        ExpectedStrength.NONE,
        "Controle negativo. PRR=1.10 na validacao",
    ),
    BenchmarkCase(
        "norepinephrine",
        "anhedonia",
        BenchmarkCategory.KNOWN_NOISE,
        ExpectedDirection.NO_SIGNAL,
        ExpectedStrength.NONE,
        "Controle negativo. PRR=0 na validacao",
    ),
    BenchmarkCase(
        "sevoflurane",
        "agranulocytosis",
        BenchmarkCategory.KNOWN_NOISE,
        ExpectedDirection.NO_SIGNAL,
        ExpectedStrength.NONE,
        "Anestesico inalatorio sem mecanismo hematologico. Par absurdo",
    ),
]

# --- REPURPOSING ---

_REPURPOSING = [
    BenchmarkCase(
        "sildenafil",
        "pulmonary hypertension",
        BenchmarkCategory.REPURPOSING,
        ExpectedDirection.SIGNAL,
        ExpectedStrength.STRONG,
        "Efeito colateral que virou indicacao aprovada (Revatio)",
    ),
]

# --- ONTOLOGY (MedDRA mapping challenges) ---

_ONTOLOGY = [
    BenchmarkCase(
        "metformin",
        "lactic acidosis",
        BenchmarkCategory.ONTOLOGY,
        ExpectedDirection.SIGNAL,
        ExpectedStrength.STRONG,
        "Teste de MedDRA grouping — 'lactic acidosis' tem sinonimos",
    ),
]

# All cases combined
BENCHMARK_CASES: list[BenchmarkCase] = [
    *_KNOWN_SIGNALS,
    *_CONFOUNDING,
    *_EMERGING,
    *_PROBLEMATIC,
    *_KNOWN_NOISE,
    *_REPURPOSING,
    *_ONTOLOGY,
]
