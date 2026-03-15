# FAERS — FDA Adverse Event Reporting System

## What is FAERS?

The FDA Adverse Event Reporting System (FAERS) is a database of adverse event reports, medication error reports, and product quality complaints submitted to the U.S. Food and Drug Administration. It is the primary post-market safety surveillance tool in the United States.

hypokrates accesses FAERS through the [openFDA API](https://open.fda.gov/apis/drug/event/), which provides a public, queryable interface to the FAERS data.

## Coverage

- **20+ million reports** from 2004 to present
- **Updated quarterly** (January, April, July, October)
- Reports from healthcare professionals, consumers, manufacturers, and attorneys
- International reports are included if submitted to the FDA

## Rate Limits

| Condition | Limit |
|-----------|-------|
| No API key | 40 requests/minute (shared across all users from same IP) |
| With API key | 240 requests/minute |

!!! tip "Getting an API key"
    Register for a free openFDA API key at [open.fda.gov/apis/authentication/](https://open.fda.gov/apis/authentication/). Then configure it:

    ```python
    from hypokrates.config import configure
    configure(openfda_api_key="your-key-here")
    ```

## Limitations

Understanding FAERS limitations is critical for interpreting results correctly.

### Voluntary Reporting

FAERS is a **spontaneous reporting system** — reports are submitted voluntarily. This means:

- Only a fraction of actual adverse events are reported (estimated 1–10%)
- Absence of a report does not mean absence of a reaction
- Reporting rates vary by drug, event severity, and media attention

### No Denominator

FAERS contains **counts of reports**, not rates. There is no information about how many people took a drug without experiencing an adverse event. You cannot calculate incidence rates from FAERS data alone.

### Duplicate Reports

The same adverse event may be reported multiple times by different parties (patient, physician, manufacturer). FDA performs some de-duplication, but duplicates remain.

### Indication Bias

Drugs used for serious conditions tend to have more serious adverse event reports — not necessarily because the drug is more dangerous, but because the underlying patient population is sicker.

### Notoriety Bias

When an adverse event receives media attention, reporting of that specific event increases disproportionately (Weber effect). This can create artificial signals.

### Missing Data

Many reports have incomplete data — patient age, sex, weight, and dose information are frequently missing. Reports with missing drug role or reaction terms are common.

## FAERS Bulk (Quarterly Files)

In addition to the OpenFDA API, hypokrates supports loading FAERS quarterly ASCII files directly into a local DuckDB store. This provides:

- **Deduplication by CASEID** — keeps only the latest version of each case (follow-ups/corrections are collapsed)
- **Role filtering** — query by Primary Suspect only (PS), PS+SS (suspect), or all roles (including concomitant)
- **Direction analysis** — compare PRR across different role filters to distinguish pharmacological signals from confounding

### Loading quarterly files

```python
from hypokrates.sync import faers_bulk

# Load one or more quarters
from hypokrates.faers_bulk.store import FAERSBulkStore
store = FAERSBulkStore.get_instance()
store.load_quarter("/path/to/faers_ascii_2024Q3.zip")
store.load_quarter("/path/to/faers_ascii_2024Q4.zip")
```

Quarterly ASCII ZIPs can be downloaded from [FDA FAERS Downloads](https://fis.fda.gov/extensions/FPD-QDE-FAERS/FPD-QDE-FAERS.html). Each ZIP is ~300-500 MB.

### Using bulk in scan

When bulk data is loaded, `scan_drug()` automatically uses it for event discovery:

```python
result = scan.scan_drug(
    "propofol",
    primary_suspect_only=True,  # PS-only (bulk only)
    check_direction=True,       # compare base vs PS-only PRR
)
print(result.bulk_mode)          # True
print(result.role_filter_used)   # "ps_only"
```

### Storage

Bulk data is stored at `~/.cache/hypokrates/faers_bulk.duckdb` (separate from the HTTP cache).
