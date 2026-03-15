"""Clusters semânticos para agrupamento de eventos adversos por sistema clínico.

Organiza eventos do scan em categorias clínicas para facilitar
interpretação, especialmente em análise de classe terapêutica.
"""

from __future__ import annotations

# Mapeamento de termos MedDRA → cluster clínico
# Um termo pode pertencer a apenas um cluster
# Termos não mapeados ficam em "Other"

SEMANTIC_CLUSTERS: dict[str, list[str]] = {
    "Cardiovascular": [
        "BRADYCARDIA",
        "TACHYCARDIA",
        "HYPOTENSION",
        "HYPERTENSION",
        "QT PROLONGATION",
        "ATRIAL FIBRILLATION",
        "VENTRICULAR FIBRILLATION",
        "CARDIAC ARREST",
        "CARDIAC FAILURE",
        "CARDIAC FAILURE CONGESTIVE",
        "MYOCARDIAL INFARCTION",
        "PALPITATIONS",
        "DEEP VEIN THROMBOSIS",
        "PULMONARY EMBOLISM",
        "BLOOD PRESSURE SYSTOLIC INCREASED",
        "BLOOD PRESSURE FLUCTUATION",
        "SYNCOPE",
        "ARRHYTHMIA",
        "CARDIOMYOPATHY",
        "EJECTION FRACTION DECREASED",
    ],
    "Endocrine/Metabolic": [
        "HYPERGLYCAEMIA",
        "HYPOGLYCAEMIA",
        "ADRENAL INSUFFICIENCY",
        "CUSHING'S SYNDROME",
        "HYPERTHYROIDISM",
        "HYPOTHYROIDISM",
        "DIABETES MELLITUS",
        "WEIGHT INCREASED",
        "WEIGHT DECREASED",
        "HYPERKALAEMIA",
        "HYPONATRAEMIA",
        "HYPOCALCAEMIA",
        "METABOLIC ACIDOSIS",
        "HYPERTRIGLYCERIDEMIA",
        "HYPERLIPIDAEMIA",
    ],
    "Psychiatric": [
        "INSOMNIA",
        "DEPRESSION",
        "ANXIETY",
        "PSYCHIATRIC DISORDER",
        "MOOD DISORDER",
        "MANIA",
        "HALLUCINATION",
        "DELIRIUM",
        "AGITATION",
        "SUICIDAL IDEATION",
        "PSYCHOTIC DISORDER",
        "MENTAL STATUS CHANGES",
        "EMOTIONAL DISTRESS",
        "CONFUSION",
        "SOMNOLENCE",
        "ANHEDONIA",
    ],
    "Musculoskeletal": [
        "OSTEONECROSIS",
        "OSTEOPOROSIS",
        "RHABDOMYOLYSIS",
        "MUSCULAR WEAKNESS",
        "MYALGIA",
        "ARTHRALGIA",
        "ARTHROPATHY",
        "JOINT SWELLING",
        "MUSCULOSKELETAL STIFFNESS",
        "BACK PAIN",
        "PAIN IN EXTREMITY",
        "FRACTURE",
        "TENDON RUPTURE",
    ],
    "Hepatic": [
        "HEPATOTOXICITY",
        "HEPATITIS",
        "JAUNDICE",
        "LIVER FUNCTION TEST ABNORMAL",
        "ALANINE AMINOTRANSFERASE INCREASED",
        "ASPARTATE AMINOTRANSFERASE INCREASED",
        "BILIRUBIN INCREASED",
        "CHOLESTASIS",
    ],
    "Renal": [
        "RENAL FAILURE",
        "NEPHRITIS",
        "PROTEINURIA",
        "HAEMATURIA",
        "CREATININE INCREASED",
        "BLOOD UREA INCREASED",
    ],
    "Respiratory": [
        "RESPIRATORY DEPRESSION",
        "BRONCHOSPASM",
        "LARYNGOSPASM",
        "DYSPNOEA",
        "COUGH",
        "PNEUMONIA",
        "PULMONARY TOXICITY",
        "PULMONARY FIBROSIS",
        "OXYGEN SATURATION DECREASED",
    ],
    "Haematologic": [
        "THROMBOCYTOPENIA",
        "AGRANULOCYTOSIS",
        "ANAEMIA",
        "PANCYTOPENIA",
        "FEBRILE NEUTROPENIA",
        "WHITE BLOOD CELL COUNT DECREASED",
        "COAGULOPATHY",
        "DISSEMINATED INTRAVASCULAR COAGULATION",
        "INTERNATIONAL NORMALISED RATIO INCREASED",
    ],
    "Dermatologic": [
        "STEVENS-JOHNSON SYNDROME",
        "ANGIOEDEMA",
        "RASH",
        "PRURITUS",
        "URTICARIA",
        "ALOPECIA",
        "HYPERHIDROSIS",
        "PHOTOSENSITIVITY REACTION",
    ],
    "Gastrointestinal": [
        "NAUSEA AND VOMITING",
        "DIARRHOEA",
        "CONSTIPATION",
        "PANCREATITIS",
        "ABDOMINAL PAIN",
        "ABDOMINAL PAIN UPPER",
        "ABDOMINAL DISCOMFORT",
        "GASTROINTESTINAL HAEMORRHAGE",
        "STOMATITIS",
    ],
    "Neurologic": [
        "SEIZURE",
        "DIZZINESS",
        "HEADACHE",
        "NEUROPATHY PERIPHERAL",
        "TREMOR",
        "DYSKINESIA",
        "PARAESTHESIA",
        "HYPOAESTHESIA",
        "GAIT DISTURBANCE",
        "ATAXIA",
        "SEROTONIN SYNDROME",
        "NEUROLEPTIC MALIGNANT SYNDROME",
        "MALIGNANT HYPERTHERMIA",
    ],
    "Immune/Infection": [
        "ANAPHYLAXIS",
        "INFECTION",
        "SEPSIS",
        "SEPTIC SHOCK",
        "SINUSITIS",
        "NASOPHARYNGITIS",
        "URINARY TRACT INFECTION",
        "CYSTITIS",
        "IMMUNOSUPPRESSION",
        "CYTOKINE RELEASE SYNDROME",
    ],
    "Ophthalmic": [
        "CATARACT",
        "GLAUCOMA",
        "VISION BLURRED",
        "VISUAL IMPAIRMENT",
        "CENTRAL SEROUS CHORIORETINOPATHY",
    ],
}

# Build reverse lookup: term → cluster name
_TERM_TO_CLUSTER: dict[str, str] = {}
for _cluster_name, _terms in SEMANTIC_CLUSTERS.items():
    for _term in _terms:
        _TERM_TO_CLUSTER[_term.upper()] = _cluster_name

DEFAULT_CLUSTER = "Other"


def get_cluster(event: str) -> str:
    """Retorna o cluster semântico de um evento.

    Args:
        event: Termo MedDRA (e.g., "BRADYCARDIA").

    Returns:
        Nome do cluster (e.g., "Cardiovascular") ou "Other" se não mapeado.
    """
    return _TERM_TO_CLUSTER.get(event.upper().strip(), DEFAULT_CLUSTER)


def cluster_events(events: list[str]) -> dict[str, list[str]]:
    """Agrupa uma lista de eventos por cluster semântico.

    Args:
        events: Lista de termos MedDRA.

    Returns:
        Dict de cluster_name → lista de eventos.
    """
    clusters: dict[str, list[str]] = {}
    for event in events:
        cluster = get_cluster(event)
        if cluster not in clusters:
            clusters[cluster] = []
        clusters[cluster].append(event)
    return clusters
