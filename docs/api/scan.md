# Scan API

Automated scanning of top adverse events for a drug, with parallel hypothesis generation.

## `scan_drug()`

Scans the top N adverse events for a drug in FAERS and runs hypothesis classification for each.

=== "Async"

    ```python
    from hypokrates.scan import api as scan

    result = await scan.scan_drug("propofol", top_n=20)
    for item in result.items:
        print(f"#{item.rank} {item.event}: {item.classification.value} (score={item.score:.1f})")
    ```

=== "Sync"

    ```python
    from hypokrates.sync import scan

    result = scan.scan_drug("propofol", top_n=20)
    for item in result.items:
        print(f"#{item.rank} {item.event}: {item.classification.value} (score={item.score:.1f})")
    ```

### Parameters

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `drug` | `str` | required | Generic drug name |
| `top_n` | `int` | `20` | Number of top events to scan |
| `concurrency` | `int` | `5` | Max parallel hypothesis evaluations |
| `include_no_signal` | `bool` | `False` | Include events with no signal in results |
| `use_cache` | `bool` | `True` | Use DuckDB cache |
| `check_labels` | `bool` | `False` | Check FDA label via DailyMed |
| `check_trials` | `bool` | `False` | Search ClinicalTrials.gov |
| `check_drugbank` | `bool` | `False` | Check DrugBank for mechanism/interactions |
| `check_opentargets` | `bool` | `False` | Check OpenTargets for LRT scores |
| `check_chembl` | `bool` | `False` | Check ChEMBL for mechanism/targets |
| `group_events` | `bool` | `True` | Group synonymous MedDRA terms |
| `filter_operational` | `bool` | `True` | Filter operational/regulatory MedDRA terms |
| `suspect_only` | `bool` | `False` | Only count reports where drug is suspect |
| `check_coadmin` | `bool` | `False` | Check co-administration confounding (+1 API call/event) |
| `on_progress` | `Callable` | `None` | Progress callback `(completed, total, event_term)` |

### Performance

Each event requires ~5 HTTP requests (4 FAERS + 1 PubMed):

- **Without API key** (FAERS 40/min): ~2-3 minutes for 20 events
- **With API key** (FAERS 240/min): ~30-60 seconds for 20 events

### Scoring

Items are ranked by a composite score:

```
score = classification_weight x max(avg(PRR_lci, ROR_lci), 0.1)
```

Weights: novel=10.0, emerging=5.0, known=1.0, no_signal=0.0

Additional multipliers:
- `LABEL_NOT_IN_MULTIPLIER = 1.5` (boost if not in FDA label)
- `LABEL_IN_MULTIPLIER = 0.5` (penalty if in FDA label)
- `INDICATION_MULTIPLIER = 0.3` (penalty for indication terms)
- `CO_ADMIN_MULTIPLIER = 0.3` (penalty for co-administration confounding)

## Models

### `ScanItem`

| Field | Type | Description |
|-------|------|-------------|
| `drug` | `str` | Drug name |
| `event` | `str` | Adverse event term |
| `classification` | `HypothesisClassification` | novel/emerging/known/no_signal |
| `signal` | `SignalResult` | Full signal detection result |
| `literature_count` | `int` | PubMed paper count |
| `articles` | `list[PubMedArticle]` | Article metadata |
| `evidence` | `EvidenceBlock` | Provenance block |
| `summary` | `str` | Human-readable summary |
| `score` | `float` | Composite ranking score |
| `rank` | `int` | Rank (1 = highest score) |
| `in_label` | `bool \| None` | Whether event is in FDA label |
| `volume_flag` | `bool` | True if reports exceed anomaly threshold (2000) |
| `is_indication` | `bool` | True if event is a known drug indication |
| `coadmin_flag` | `bool` | True if co-administration confounding detected |
| `coadmin_detail` | `str \| None` | Summary of co-admin analysis |
| `cluster` | `str` | Semantic cluster (e.g., "Cardiovascular") |

### `ScanResult`

| Field | Type | Description |
|-------|------|-------------|
| `drug` | `str` | Drug name |
| `items` | `list[ScanItem]` | Results sorted by score desc |
| `total_scanned` | `int` | Total events scanned |
| `novel_count` | `int` | Novel hypothesis count |
| `emerging_count` | `int` | Emerging signal count |
| `known_count` | `int` | Known association count |
| `no_signal_count` | `int` | No signal count |
| `labeled_count` | `int` | Events found in FDA label |
| `failed_count` | `int` | Failed hypothesis evaluations |
| `groups_applied` | `bool` | Whether MedDRA grouping was applied |
| `filtered_operational_count` | `int` | Operational MedDRA terms filtered |
| `coadmin_flagged_count` | `int` | Events flagged as co-admin confounding |
| `skipped_events` | `list[str]` | Events that failed |
| `mechanism` | `str \| None` | Drug mechanism of action |
| `meta` | `MetaInfo` | Provenance metadata |
