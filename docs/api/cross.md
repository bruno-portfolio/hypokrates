# Cross-Reference API

Cross-reference FAERS signal detection with PubMed literature to classify drug–event hypotheses.

```python
from hypokrates.cross import api as cross  # async
from hypokrates.sync import cross           # sync
```

!!! danger "Research tool — not for clinical decisions"
    hypokrates output is for **screening and hypothesis generation only**. Classification is based on heuristic thresholds. Always validate findings through established pharmacovigilance processes before any clinical action.

---

## `hypothesis()`

Run the full pipeline: FAERS signal detection + PubMed literature search (in parallel via `asyncio.gather`), then classify the result.

```python
result = await cross.hypothesis("propofol", "bradycardia")
print(result.classification)   # HypothesisClassification enum
print(result.summary)          # Human-readable summary
print(result.signal)           # Full SignalResult
print(result.literature_count) # Number of PubMed papers
print(result.articles)         # PubMedArticle list
```

**Parameters**

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `drug` | `str` | *required* | Generic drug name |
| `event` | `str` | *required* | Adverse event term |
| `novel_max` | `int` | `0` | Max papers for `novel_hypothesis` classification |
| `emerging_max` | `int` | `5` | Max papers for `emerging_signal` classification |
| `literature_limit` | `int` | `5` | Max articles returned from PubMed |
| `use_mesh` | `bool` | `False` | Use MeSH qualifiers for PubMed search |
| `check_label` | `bool` | `False` | Check FDA label via DailyMed |
| `check_trials` | `bool` | `False` | Search ClinicalTrials.gov |
| `check_drugbank` | `bool` | `False` | Check DrugBank for mechanism/interactions |
| `check_opentargets` | `bool` | `False` | Check OpenTargets for LRT score |
| `check_chembl` | `bool` | `False` | Check ChEMBL for mechanism/targets |
| `check_coadmin` | `bool` | `False` | Analyze co-administration confounding (Layer 1 + 2) |
| `suspect_only` | `bool` | `False` | Only count reports where drug is suspect |
| `use_cache` | `bool` | `True` | Use DuckDB cache |

All optional enrichments (`check_label`, `check_trials`, `check_drugbank`, `check_opentargets`, `check_chembl`, `check_coadmin`, `check_onsides`, `check_pharmgkb`, `check_canada`, `check_jader`) degrade gracefully — if any external source is unavailable, a warning is logged and the corresponding field is set to `None` instead of raising an exception.

**Returns:** [`HypothesisResult`](#hypothesisresult)

---

## Classification Logic

```mermaid
flowchart TD
    A[hypothesis drug, event] --> B{FAERS signal detected?}
    B -- No --> B2{In FDA label AND papers > emerging_max?}
    B2 -- Yes --> G[known_association]
    B2 -- No --> B3{Papers > emerging_max?}
    B3 -- Yes --> F[emerging_signal]
    B3 -- No --> C[no_signal]
    B -- Yes --> D{PubMed papers count}
    D -- "papers <= novel_max (0)" --> E[novel_hypothesis]
    D -- "papers <= emerging_max (5)" --> F
    D -- "papers > emerging_max" --> G
```

### Classification Table

| Signal Detected | In Label | Papers | Classification | Confidence |
|:-:|:-:|:-:|---|---|
| No | — | 0–5 | `no_signal` | n/a |
| No | No | > 5 | `emerging_signal` | moderate |
| No | Yes | > 5 | `known_association` | high |
| Yes | — | 0 | `novel_hypothesis` | low |
| Yes | — | 1–5 | `emerging_signal` | moderate |
| Yes | — | > 5 | `known_association` | high |

> **Note:** Even without a FAERS disproportionality signal, substantial literature and/or FDA label confirmation can indicate a known association. FAERS signals can be absent for well-known adverse events when the drug has very high reporting volume (signal dilution) or when the event is extremely common across all drugs.

### Custom Thresholds

The default thresholds (`novel_max=0`, `emerging_max=5`) are heuristics. Adjust for your domain:

```python
# Stricter — require more literature for "known"
result = await cross.hypothesis(
    "propofol", "bradycardia",
    novel_max=0,
    emerging_max=20,
)

# Looser — for well-studied drug classes
result = await cross.hypothesis(
    "aspirin", "bleeding",
    novel_max=2,
    emerging_max=10,
)
```

---

## Models

### `HypothesisClassification`

`StrEnum` with four values:

| Value | Description |
|-------|-------------|
| `novel_hypothesis` | FAERS signal but no published literature — potential new finding |
| `emerging_signal` | FAERS signal with limited literature — monitor closely |
| `known_association` | FAERS signal with substantial literature — well-documented |
| `no_signal` | No disproportionality signal in FAERS |

### `HypothesisResult`

| Field | Type | Description |
|-------|------|-------------|
| `drug` | `str` | Drug name |
| `event` | `str` | Event term |
| `classification` | `HypothesisClassification` | Hypothesis category |
| `signal` | `SignalResult` | Full signal detection result |
| `literature_count` | `int` | Total PubMed papers found |
| `articles` | `list[PubMedArticle]` | Article metadata |
| `evidence` | `EvidenceBlock` | Provenance and limitations |
| `summary` | `str` | Human-readable summary |
| `thresholds_used` | `dict[str, int]` | `{"novel_max": 0, "emerging_max": 5}` |
| `in_label` | `bool \| None` | Whether event is in FDA label (if `check_label=True`) |
| `active_trials` | `int \| None` | Active clinical trials (if `check_trials=True`) |
| `mechanism` | `str \| None` | Drug mechanism of action (if DrugBank/ChEMBL checked) |
| `ot_llr` | `float \| None` | OpenTargets log-likelihood ratio (if `check_opentargets=True`) |
| `coadmin` | `CoAdminAnalysis \| None` | Co-administration analysis (if `check_coadmin=True`) |
| `onsides_sources` | `list[str] \| None` | International label sources (if `check_onsides=True`) |
| `pharmacogenomics` | `list[str]` | PharmGKB annotations (if `check_pharmgkb=True`) |
| `canada_reports` | `int \| None` | Canada Vigilance report count (if `check_canada=True`) |
| `canada_signal` | `bool \| None` | Canada Vigilance signal detected (if `check_canada=True`) |
| `jader_reports` | `int \| None` | JADER report count (if `check_jader=True`) |
| `jader_signal` | `bool \| None` | JADER signal detected (if `check_jader=True`) |

### `CoAdminAnalysis`

Result of co-administration confounding analysis (Layer 1 + Layer 2).

| Field | Type | Description |
|-------|------|-------------|
| `profile` | `CoSuspectProfile` | Layer 1: co-suspect statistics |
| `overlap_ratio` | `float` | Fraction of top-event-drugs that are co-suspects (0–1) |
| `specificity_ratio` | `float \| None` | Drug PRR / median co-drug PRR (if computed) |
| `is_specific` | `bool` | `True` = drug-specific signal |
| `co_signals` | `list[CoSignalItem]` | PRR for each co-drug tested |
| `verdict` | `str` | `"specific"`, `"co_admin_artifact"`, or `"inconclusive"` |

### `CoSignalItem`

| Field | Type | Description |
|-------|------|-------------|
| `drug` | `str` | Co-drug name |
| `prr` | `float` | PRR for the co-drug + event |
| `signal_detected` | `bool` | Whether signal was detected |

---

## `investigate()`

Deep investigation combining full `hypothesis()` (all enrichments enabled) with demographic stratification from FAERS Bulk and Canada Vigilance. Runs everything in parallel via `asyncio.gather()`.

```python
from hypokrates.cross.investigate import investigate

result = await investigate("atorvastatin", "myalgia")
print(result.hypothesis.classification)  # HypothesisClassification
print(result.demographic_summary)        # Textual summary

for s in result.sex_strata:
    print(f"  {s.source} {s.stratum_value}: PRR={s.prr:.2f}, signal={s.signal_detected}")

for s in result.country_strata:
    print(f"  {s.stratum_value}: {s.drug_event_count} reports, signal={s.signal_detected}")
```

**Parameters**

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `drug` | `str` | *required* | Generic drug name |
| `event` | `str` | *required* | Adverse event term (MedDRA PT) |
| `suspect_only` | `bool` | `False` | Only count reports where drug is suspect |
| `use_cache` | `bool` | `True` | Use DuckDB cache |

**Stratification queries:**

- **FAERS Bulk**: 6 queries (sex M/F + age 0-17/18-44/45-64/65+)
- **Canada Vigilance**: 2 queries (sex M/F)
- **Cross-country**: extracted from hypothesis result (FAERS/Canada/JADER)

All strata queries are DuckDB local — zero rate limits, ~50ms each. If FAERS Bulk or Canada store is not loaded, those strata return empty (graceful degradation).

**Returns:** [`InvestigationResult`](#investigationresult)

---

## Strata Models

### `StratumSignal`

Signal for a single demographic stratum.

| Field | Type | Description |
|-------|------|-------------|
| `source` | `str` | Data source (`"FAERS"`, `"Canada"`, `"JADER"`) |
| `stratum_type` | `str` | `"sex"`, `"age_group"`, or `"country"` |
| `stratum_value` | `str` | Stratum value (`"M"`, `"F"`, `"0-17"`, `"65+"`, etc.) |
| `drug_event_count` | `int` | Reports in this stratum |
| `prr` | `float` | PRR for this stratum |
| `ror` | `float` | ROR for this stratum |
| `ic` | `float` | IC for this stratum |
| `signal_detected` | `bool` | Whether signal was detected |
| `insufficient_data` | `bool` | `True` if stratum has too few reports |

### `InvestigationResult`

| Field | Type | Description |
|-------|------|-------------|
| `hypothesis` | `HypothesisResult` | Full hypothesis result (all enrichments) |
| `sex_strata` | `list[StratumSignal]` | Sex stratification (FAERS + Canada) |
| `age_strata` | `list[StratumSignal]` | Age group stratification (FAERS only) |
| `country_strata` | `list[StratumSignal]` | Cross-country comparison (FAERS/Canada/JADER) |
| `demographic_summary` | `str` | Human-readable summary of demographic differences |
| `meta` | `MetaInfo` | Provenance metadata |
