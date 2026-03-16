# OnSIDES

[OnSIDES](https://github.com/tatonetti-lab/onsides) (Observational Studies of drug Side Effects) contains 7.1M drug-ADE pairs extracted by PubMedBERT from 51,460 drug labels across 4 countries (US, EU, UK, JP). F1=0.935.

## Setup

1. Download the OnSIDES ZIP (313MB) from the project's GitHub releases
2. Extract the 7 CSV files to a directory
3. Configure the path:

```python
from hypokrates.config import configure

configure(onsides_path="/path/to/onsides/csvs/")
```

The CSV files are loaded into a local DuckDB store (`~/.cache/hypokrates/onsides.duckdb`) on first use.

## API

### `onsides_events(drug, *, min_confidence=0.5)`

Returns all adverse events found in international labels for a drug.

```python
from hypokrates.sync import onsides

result = onsides.onsides_events("propofol")
for ev in result.events[:10]:
    print(f"{ev.meddra_name}: {ev.confidence:.2f} ({', '.join(ev.sources)})")
```

**Parameters:**
- `drug` — Generic drug name (RxNorm ingredient)
- `min_confidence` — Minimum PubMedBERT prediction confidence (0-1, default 0.5)

**Returns:** `OnSIDESResult` with events sorted by confidence descending.

### `onsides_check_event(drug, event)`

Check if a specific event appears in any country's label for a drug.

```python
check = onsides.onsides_check_event("propofol", "bradycardia")
if check:
    print(f"Found in {check.num_sources}/4 countries: {', '.join(check.sources)}")
    print(f"Section: {check.label_section}, Confidence: {check.confidence:.3f}")
```

**Returns:** `OnSIDESEvent` or `None`.

## Models

### `OnSIDESEvent`

| Field | Type | Description |
|-------|------|-------------|
| `meddra_id` | `int` | MedDRA concept ID |
| `meddra_name` | `str` | MedDRA preferred term |
| `label_section` | `str` | BW (Boxed Warning), WP (Warnings/Precautions), AR (Adverse Reactions) |
| `confidence` | `float` | PubMedBERT prediction confidence (0-1) |
| `sources` | `list[str]` | Countries where found (US, EU, UK, JP) |
| `num_sources` | `int` | Number of countries |

## Integration with hypothesis()

```python
from hypokrates.sync import cross

result = cross.hypothesis(
    "propofol", "bradycardia",
    check_onsides=True,  # adds onsides_sources to result
)
if result.onsides_sources:
    print(f"Listed in {len(result.onsides_sources)}/4 country labels")
```

## Data

- **Source:** OnSIDES (Tatonetti Lab, Columbia University)
- **Size:** 313MB ZIP, 7 CSV files
- **Coverage:** 51,460 labels, 7.1M drug-ADE pairs
- **Countries:** US (FDA), EU (EMA), UK (MHRA), JP (PMDA)
- **Method:** PubMedBERT NLP extraction (F1=0.935)
- **License:** See OnSIDES project for terms
