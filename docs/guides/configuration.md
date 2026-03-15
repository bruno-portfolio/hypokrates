# Configuration

hypokrates uses a global singleton configuration that can be set once and applies to all subsequent API calls.

## `configure()`

```python
from hypokrates.config import configure

configure(
    openfda_api_key="your-openfda-key",
    ncbi_api_key="your-ncbi-key",
    ncbi_email="you@example.com",
    drugbank_path="/path/to/drugbank.xml",
    cache_enabled=True,
    cache_dir="/path/to/cache",
    http_timeout=30.0,
    http_max_retries=3,
    debug=False,
)
```

All parameters are optional — only set what you need. Unset fields keep their defaults.

## Parameters

### API Keys

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `openfda_api_key` | `str \| None` | `None` | OpenFDA API key — raises rate limit from 40 to 240 req/min |
| `ncbi_api_key` | `str \| None` | `None` | NCBI API key — raises rate limit from 180 to 600 req/min |
| `ncbi_email` | `str \| None` | `None` | Email for NCBI requests (recommended by NCBI) |

!!! tip "Where to get API keys"
    - **OpenFDA:** Register at [open.fda.gov/apis/authentication/](https://open.fda.gov/apis/authentication/) — free, instant
    - **NCBI:** Register at [ncbiinsights.ncbi.nlm.nih.gov](https://ncbiinsights.ncbi.nlm.nih.gov/2017/11/02/new-api-keys-for-the-e-utilities/) — free, instant

### Data Sources

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `drugbank_path` | `str \| Path \| None` | `None` | Path to DrugBank XML file (~175MB). Required for `drug_info()` and `drug_interactions()`. Free academic license at [go.drugbank.com](https://go.drugbank.com/releases/latest). |
| `anvisa_csv_path` | `str \| Path \| None` | `None` | Path to ANVISA medicamentos CSV. Optional — auto-downloaded on first call if not set. |

### Cache

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `cache_enabled` | `bool` | `True` | Enable/disable DuckDB cache globally |
| `cache_dir` | `Path` | `~/.cache/hypokrates` | Directory for the DuckDB cache file |

The cache stores HTTP responses locally with source-specific TTLs. This reduces API calls and speeds up repeated queries.

| Source | Default TTL |
|--------|-------------|
| FAERS | 24 hours |
| PubMed | 24 hours |
| RxNorm / MeSH | 90 days |
| DailyMed | 30 days |
| ClinicalTrials.gov | 24 hours |
| OpenTargets | 7 days |
| ChEMBL | 7 days |

To disable cache for a single call, use `use_cache=False`:

```python
result = await faers.adverse_events("propofol", use_cache=False)
```

### HTTP

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `http_timeout` | `float` | `30.0` | Request timeout in seconds |
| `http_max_retries` | `int` | `3` | Maximum retry attempts on failure |

Retries use exponential backoff. Status codes 429 (rate limit), 500, 502, 503, and 504 trigger retries.

### Debug

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `debug` | `bool` | `False` | Enable verbose logging |

When `True`, logs detailed HTTP request/response information to the `hypokrates` logger.

## Optional Dependencies

Some features require additional packages:

```bash
# ClinicalTrials.gov (Cloudflare TLS bypass)
pip install hypokrates[trials]

# MCP server
pip install hypokrates[mcp]

# All extras
pip install hypokrates[trials,mcp]
```

## Reading Configuration

```python
from hypokrates.config import get_config

config = get_config()
print(config.cache_dir)
print(config.http_timeout)
```

## Reset

For testing, you can reset to defaults:

```python
from hypokrates.config import reset_config
reset_config()
```

## Environment Variables

hypokrates currently reads configuration from code only (`configure()`). Environment variable support is planned for a future release. For now, a common pattern:

```python
import os
from hypokrates.config import configure

configure(
    openfda_api_key=os.getenv("OPENFDA_API_KEY"),
    ncbi_api_key=os.getenv("NCBI_API_KEY"),
    ncbi_email=os.getenv("NCBI_EMAIL"),
    drugbank_path=os.getenv("DRUGBANK_PATH"),
)
```
