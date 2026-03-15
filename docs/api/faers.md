# FAERS API

Query the FDA Adverse Event Reporting System (FAERS) via OpenFDA.

```python
from hypokrates.faers import api as faers  # async
from hypokrates.sync import faers          # sync
```

---

## `adverse_events()`

Fetch individual adverse event reports for a drug.

```python
result = await faers.adverse_events(
    "propofol",
    age_min=18,
    age_max=65,
    sex="F",
    serious=True,
    limit=50,
)
```

**Parameters**

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `drug` | `str` | *required* | Generic drug name (e.g., `"propofol"`) |
| `age_min` | `int \| None` | `None` | Minimum patient age |
| `age_max` | `int \| None` | `None` | Maximum patient age |
| `sex` | `str \| None` | `None` | `"M"` or `"F"` |
| `serious` | `bool \| None` | `None` | `True` for serious reports only |
| `limit` | `int` | `100` | Maximum number of reports returned |
| `use_cache` | `bool` | `True` | Use DuckDB cache |

**Returns:** [`FAERSResult`](#faersresult)

---

## `top_events()`

Get the most frequently reported adverse events for a drug.

```python
result = await faers.top_events("propofol", limit=10)
for event in result.events:
    print(f"{event.term}: {event.count}")
```

**Parameters**

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `drug` | `str` | *required* | Generic drug name |
| `limit` | `int` | `10` | Number of top events |
| `use_cache` | `bool` | `True` | Use DuckDB cache |

**Returns:** [`FAERSResult`](#faersresult) (with `events` populated)

---

## `compare()`

Compare adverse events between multiple drugs.

```python
results = await faers.compare(
    ["propofol", "midazolam"],
    outcome="DEATH",
    limit=10,
)
for drug_name, result in results.items():
    print(f"{drug_name}: {result.meta.total_results} reports")
```

**Parameters**

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `drugs` | `list[str]` | *required* | List of generic drug names |
| `outcome` | `str \| None` | `None` | Filter by specific reaction term |
| `limit` | `int` | `10` | Top N events per drug |
| `use_cache` | `bool` | `True` | Use DuckDB cache |

**Returns:** `dict[str, FAERSResult]` — drug name to result mapping

!!! note
    When `outcome` is provided, fetches reports filtered by that reaction. Otherwise, calls `top_events()` for each drug.

---

## `drugs_by_event()`

Reverse lookup: get the top drugs reported for a given adverse event.

```python
result = await faers.drugs_by_event("anaphylactic shock", limit=10)
for d in result.drugs:
    print(f"{d.name}: {d.count} reports")
```

**Parameters**

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `event` | `str` | *required* | MedDRA adverse event term |
| `suspect_only` | `bool` | `False` | Only count reports where drug is suspect |
| `limit` | `int` | `10` | Number of top drugs |
| `use_cache` | `bool` | `True` | Use DuckDB cache |

**Returns:** `DrugsByEventResult`

---

## `co_suspect_profile()`

Analyze co-suspect drug patterns for a drug+event pair. Fetches individual reports and counts how many suspect drugs appear per report. Useful for detecting co-administration confounding (e.g., OR setting where propofol, fentanyl, rocuronium are all listed as suspect for the same event).

```python
profile = await faers.co_suspect_profile("propofol", "anaphylactic shock")
print(f"Median suspects/report: {profile.median_suspects}")
print(f"Co-admin flag: {profile.co_admin_flag}")
for drug_name, count in profile.top_co_drugs:
    print(f"  {drug_name}: {count}")
```

**Parameters**

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `drug` | `str` | *required* | Generic drug name |
| `event` | `str` | *required* | MedDRA adverse event term |
| `sample_size` | `int` | `100` | Number of reports to analyze |
| `suspect_only` | `bool` | `False` | Only count reports where drug is suspect |
| `use_cache` | `bool` | `True` | Use DuckDB cache |

**Returns:** [`CoSuspectProfile`](#cosuspectprofile)

!!! warning "Co-administration confounding"
    A high `median_suspects` (>3) indicates a procedural setting (e.g., operating room) where multiple drugs are routinely administered together. The PRR may be inflated by ubiquity, not causality. Use `coadmin_analysis()` from the Cross API for full Layer 2 analysis.

---

## Models

### `FAERSResult`

Top-level result from any FAERS query.

| Field | Type | Description |
|-------|------|-------------|
| `reports` | `list[FAERSReport]` | Individual safety reports |
| `events` | `list[AdverseEvent]` | Aggregated event counts (from `top_events`) |
| `drugs` | `list[Drug]` | Drug list (future use) |
| `meta` | `MetaInfo` | Provenance metadata |

### `FAERSReport`

Individual FAERS safety report.

| Field | Type | Description |
|-------|------|-------------|
| `safety_report_id` | `str` | Unique report identifier |
| `receive_date` | `str \| None` | Date FDA received the report |
| `receipt_date` | `str \| None` | Date of most recent update |
| `serious` | `bool` | Whether the report is classified as serious |
| `serious_reasons` | `list[str]` | Reasons for seriousness (death, hospitalization, etc.) |
| `patient` | `PatientProfile` | Patient demographics |
| `drugs` | `list[FAERSDrug]` | Drugs in the report |
| `reactions` | `list[FAERSReaction]` | Reported reactions |
| `country` | `str \| None` | Country of report origin |
| `source_type` | `str \| None` | Reporter type |

### `FAERSReaction`

| Field | Type | Description |
|-------|------|-------------|
| `term` | `str` | MedDRA preferred term |
| `outcome` | `str \| None` | Reaction outcome |
| `version` | `str \| None` | MedDRA version |

### `FAERSDrug`

| Field | Type | Description |
|-------|------|-------------|
| `name` | `str` | Drug name |
| `role` | `str \| None` | Role: `"PS"` (primary suspect), `"SS"`, `"C"`, `"I"` |
| `route` | `str \| None` | Administration route |
| `dose` | `str \| None` | Dose information |
| `indication` | `str \| None` | Reason for use |

### `AdverseEvent`

Aggregated event from count queries.

| Field | Type | Description |
|-------|------|-------------|
| `term` | `str` | MedDRA preferred term |
| `count` | `int` | Number of reports |
| `serious` | `bool \| None` | Seriousness flag |
| `outcome` | `str \| None` | Outcome |

## Filtering

### Sex Codes

The `sex` parameter accepts `"M"` or `"F"`. Internally mapped to FAERS codes (`1` = male, `2` = female).

### Serious Reports

Set `serious=True` to filter for reports classified as serious by the FDA (death, hospitalization, life-threatening, disability, congenital anomaly, other medically important).

### Age Ranges

Use `age_min` and `age_max` to filter by patient age at onset. Both are optional and can be used independently.

### `CoSuspectProfile`

| Field | Type | Description |
|-------|------|-------------|
| `drug` | `str` | Index drug name |
| `event` | `str` | Adverse event term |
| `sample_size` | `int` | Number of reports analyzed |
| `median_suspects` | `float` | Median suspect drugs per report |
| `mean_suspects` | `float` | Mean suspect drugs per report |
| `max_suspects` | `int` | Max suspects in a single report |
| `top_co_drugs` | `list[tuple[str, int]]` | Most frequent co-suspect drugs (name, count) |
| `co_admin_flag` | `bool` | `True` if `median_suspects > 3.0` |

### `DrugsByEventResult`

| Field | Type | Description |
|-------|------|-------------|
| `event` | `str` | MedDRA event term (uppercased) |
| `drugs` | `list[DrugCount]` | Drugs ordered by report count |
| `meta` | `MetaInfo` | Provenance metadata |
