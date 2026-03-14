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
