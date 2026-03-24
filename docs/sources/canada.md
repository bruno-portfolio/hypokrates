# Canada Vigilance

[Canada Vigilance](https://www.canada.ca/en/health-canada/services/drugs-health-products/medeffect-canada/adverse-reaction-database.html) is Health Canada's adverse reaction database containing ~738,000 reports from 1965 to present. Reports are MedDRA-coded (PT + SOC) and include drug role classification (Suspect/Concomitant).

## Setup

1. Download the bulk extract ZIP (325MB) from Health Canada
2. Extract the $-delimited text files to a directory
3. Configure the path:

```python
from hypokrates.config import configure

configure(canada_bulk_path="/path/to/extracted/")
```

The files are loaded into a local DuckDB store (`~/.cache/hypokrates/canada_vigilance.duckdb`) on first use.

Required files:
- `Reports.txt` — Report metadata (date, gender, age, outcome, seriousness)
- `Report_Drug.txt` — Drug-report links with role (Suspect/Concomitant)
- `Drug_Product.txt` — Drug product names
- `Drug_Product_Ingredients.txt` — Active ingredients
- `Reactions.txt` — MedDRA-coded adverse reactions (PT + SOC)

## API

### `canada_signal(drug, event, *, suspect_only=False)`

Calculate PRR for a drug-event pair in Canada Vigilance.

```python
from hypokrates.sync import canada

result = canada.canada_signal("propofol", "anaphylactic shock")
print(f"PRR: {result.prr:.2f}")
print(f"Reports: {result.drug_event_count}")
print(f"Signal: {result.signal_detected}")
```

Signal detection: PRR >= 2.0 and drug+event count >= 3.

### `canada_top_events(drug, *, limit=10, suspect_only=False)`

Top adverse events for a drug.

```python
events = canada.canada_top_events("propofol", limit=10)
for ev, count in events:
    print(f"{ev}: {count} reports")
```

### `canada_bulk_status()`

Store status with counts and date range.

```python
status = canada.canada_bulk_status()
print(f"Reports: {status.total_reports:,}")
print(f"Date range: {status.date_range}")
```

## Models

### `CanadaSignalResult`

| Field | Type | Description |
|-------|------|-------------|
| `drug` | `str` | Drug name |
| `event` | `str` | Event term |
| `drug_event_count` | `int` | Reports with drug + event |
| `drug_total` | `int` | Total reports with drug |
| `event_total` | `int` | Total reports with event |
| `total_reports` | `int` | Total reports in database |
| `prr` | `float` | Proportional Reporting Ratio |
| `signal_detected` | `bool` | PRR >= 2 and count >= 3 |

## Synonym Expansion

Drug names and event terms are automatically expanded before querying the DuckDB store:

- **Drug synonyms (INN/USAN):** "paracetamol" also matches "ACETAMINOPHEN", "adrenaline" also matches "EPINEPHRINE", etc.
- **MedDRA groups:** "malignant hyperthermia" also matches "HYPERTHERMIA MALIGNANT", etc.

This ensures cross-country comparisons with FAERS are consistent — the same drug/event pair returns results regardless of naming convention used in each database.

## Integration with hypothesis()

```python
from hypokrates.sync import cross

result = cross.hypothesis(
    "propofol", "bradycardia",
    check_canada=True,  # adds canada_reports, canada_signal to result
)
if result.canada_reports is not None:
    print(f"Canada: {result.canada_reports} reports, signal={result.canada_signal}")
```

Cross-country validation: a signal detected in both FAERS (US) and Canada Vigilance increases confidence that the association is real, not a reporting artifact.

## Data

- **Source:** Health Canada, Canada Vigilance Adverse Reaction Online Database
- **Size:** 325MB ZIP, $-delimited text files
- **Coverage:** ~738,000 reports (1965-present)
- **Coding:** MedDRA (PT + SOC), drug role (Suspect/Concomitant)
- **Updates:** Monthly
- **License:** Open Government Licence - Canada
