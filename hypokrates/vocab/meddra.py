"""Agrupamento de termos MedDRA sinônimos (dict estático, sem licença MedDRA).

Consolida preferred terms do FAERS em grupos clínicos canônicos.
Exemplo: ANAPHYLACTIC SHOCK, ANAPHYLACTIC REACTION, ANAPHYLAXIS → ANAPHYLAXIS
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from hypokrates.scan.models import ScanItem

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Grupos clínicos — canonical_term → lista de aliases
# Cada alias mapeia de volta ao canonical_term via _ALIAS_MAP
# ---------------------------------------------------------------------------

MEDDRA_GROUPS: dict[str, list[str]] = {
    "ANAPHYLAXIS": [
        "ANAPHYLACTIC REACTION",
        "ANAPHYLACTIC SHOCK",
        "ANAPHYLACTOID REACTION",
        "TYPE I HYPERSENSITIVITY",
    ],
    "CARDIAC ARREST": [
        "ASYSTOLE",
        "CARDIORESPIRATORY ARREST",
        "CARDIOPULMONARY ARREST",
    ],
    "BRADYCARDIA": [
        "SINUS BRADYCARDIA",
        "HEART RATE DECREASED",
        "BRADYARRHYTHMIA",
    ],
    "TACHYCARDIA": [
        "SINUS TACHYCARDIA",
        "HEART RATE INCREASED",
        "TACHYARRHYTHMIA",
        "SUPRAVENTRICULAR TACHYCARDIA",
    ],
    "HYPOTENSION": [
        "BLOOD PRESSURE DECREASED",
        "BLOOD PRESSURE LOW",
        "CIRCULATORY COLLAPSE",
        "HAEMODYNAMIC INSTABILITY",
    ],
    "HYPERTENSION": [
        "BLOOD PRESSURE INCREASED",
        "HYPERTENSIVE CRISIS",
    ],
    "QT PROLONGATION": [
        "ELECTROCARDIOGRAM QT PROLONGED",
        "LONG QT SYNDROME",
        "TORSADE DE POINTES",
    ],
    "RESPIRATORY DEPRESSION": [
        "RESPIRATORY FAILURE",
        "HYPOVENTILATION",
        "RESPIRATORY ARREST",
        "APNOEA",
        "APNEA",
    ],
    "BRONCHOSPASM": [
        "BRONCHIAL SPASM",
        "WHEEZING",
    ],
    "LARYNGOSPASM": [
        "LARYNGEAL SPASM",
    ],
    "SEIZURE": [
        "CONVULSION",
        "EPILEPSY",
        "STATUS EPILEPTICUS",
        "TONIC CLONIC MOVEMENTS",
    ],
    "HEPATOTOXICITY": [
        "HEPATIC FAILURE",
        "LIVER INJURY",
        "DRUG-INDUCED LIVER INJURY",
        "HEPATITIS TOXIC",
        "HEPATIC NECROSIS",
    ],
    "RENAL FAILURE": [
        "RENAL FAILURE ACUTE",
        "ACUTE KIDNEY INJURY",
        "RENAL IMPAIRMENT",
        "KIDNEY FAILURE",
    ],
    "RHABDOMYOLYSIS": [
        "MYOGLOBINURIA",
        "BLOOD CREATINE PHOSPHOKINASE INCREASED",
    ],
    "THROMBOCYTOPENIA": [
        "PLATELET COUNT DECREASED",
    ],
    "AGRANULOCYTOSIS": [
        "GRANULOCYTOPENIA",
        "NEUTROPENIA",
        "NEUTROPHIL COUNT DECREASED",
    ],
    "SEROTONIN SYNDROME": [
        "SEROTONIN TOXICITY",
    ],
    "MALIGNANT HYPERTHERMIA": [
        "HYPERTHERMIA MALIGNANT",
    ],
    "NEUROLEPTIC MALIGNANT SYNDROME": [
        "NMS",
    ],
    "NAUSEA AND VOMITING": [
        "NAUSEA",
        "VOMITING",
        "RETCHING",
        "EMESIS",
    ],
    "MYOCARDIAL INFARCTION": [
        "ACUTE MYOCARDIAL INFARCTION",
        "CORONARY ARTERY OCCLUSION",
    ],
    "VENTRICULAR FIBRILLATION": [
        "VENTRICULAR TACHYCARDIA",
        "CARDIAC FIBRILLATION",
    ],
    "PULMONARY EMBOLISM": [
        "PULMONARY THROMBOSIS",
    ],
    "STEVENS-JOHNSON SYNDROME": [
        "TOXIC EPIDERMAL NECROLYSIS",
    ],
    "ANGIOEDEMA": [
        "ANGIONEUROTIC OEDEMA",
        "ANGIOOEDEMA",
    ],
    "PANCREATITIS": [
        "PANCREATITIS ACUTE",
    ],
    "HYPERKALAEMIA": [
        "BLOOD POTASSIUM INCREASED",
        "HYPERKALEMIA",
    ],
    "HYPOGLYCAEMIA": [
        "BLOOD GLUCOSE DECREASED",
        "HYPOGLYCEMIA",
    ],
    "METHEMOGLOBINAEMIA": [
        "METHAEMOGLOBINAEMIA",
        "METHEMOGLOBINEMIA",
    ],
    "PROPOFOL INFUSION SYNDROME": [
        "PRIS",
    ],
}

# Build reverse lookup: alias → canonical term
_ALIAS_MAP: dict[str, str] = {}
for _canonical, _aliases in MEDDRA_GROUPS.items():
    for _alias in _aliases:
        _ALIAS_MAP[_alias.upper()] = _canonical


def canonical_term(event: str) -> str:
    """Retorna o termo canônico para um evento.

    Se o evento é um alias conhecido, retorna o canonical.
    Se o evento já é um canonical, retorna ele mesmo.
    Se não é conhecido, retorna o input inalterado (upper-cased).
    """
    upper = event.upper().strip()
    # É alias?
    if upper in _ALIAS_MAP:
        return _ALIAS_MAP[upper]
    # Já é canonical?
    if upper in MEDDRA_GROUPS:
        return upper
    # Desconhecido — retorna inalterado
    return upper


def group_scan_items(items: list[ScanItem]) -> list[ScanItem]:
    """Agrupa ScanItems por termo canônico MedDRA.

    Para cada grupo:
    - Mantém o item com maior score como representante
    - Merge articles (dedup por PMID)
    - Soma literature_count
    - Registra termos agrupados em grouped_terms

    Items sem grupo (canonical == original) passam inalterados.
    """
    groups: dict[str, list[ScanItem]] = {}
    for item in items:
        canonical = canonical_term(item.event)
        if canonical not in groups:
            groups[canonical] = []
        groups[canonical].append(item)

    merged: list[ScanItem] = []
    for canonical, group_items in groups.items():
        if len(group_items) == 1:
            # Sem agrupamento — item sozinho
            single = group_items[0]
            # Se o evento é alias, renomear para canonical e registrar grouped_terms
            if canonical.upper() != single.event.upper():
                single = single.model_copy(
                    update={
                        "event": canonical,
                        "grouped_terms": [single.event.upper()],
                    }
                )
            merged.append(single)
        else:
            # Múltiplos items → merge
            group_items.sort(key=lambda x: x.score, reverse=True)
            best = group_items[0]

            # Coletar todos os termos originais
            all_terms = [it.event.upper() for it in group_items]

            # Merge articles com dedup por PMID
            seen_pmids: set[str] = set()
            merged_articles = []
            for it in group_items:
                for art in it.articles:
                    if art.pmid not in seen_pmids:
                        seen_pmids.add(art.pmid)
                        merged_articles.append(art)

            # Soma literature_count
            total_lit = sum(it.literature_count for it in group_items)

            merged.append(
                best.model_copy(
                    update={
                        "event": canonical,
                        "grouped_terms": all_terms,
                        "articles": merged_articles,
                        "literature_count": total_lit,
                    }
                )
            )

    # Re-sort by score and re-rank
    merged.sort(key=lambda x: x.score, reverse=True)
    return [item.model_copy(update={"rank": idx + 1}) for idx, item in enumerate(merged)]
