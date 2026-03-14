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
| `failed_count` | `int` | Failed hypothesis evaluations |
| `skipped_events` | `list[str]` | Events that failed |
| `meta` | `MetaInfo` | Provenance metadata |
