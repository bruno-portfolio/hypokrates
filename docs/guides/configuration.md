# Configuration

hypokrates uses a global singleton configuration that can be set once and applies to all subsequent API calls.

## `configure()`

```python
from hypokrates.config import configure

configure(
    openfda_api_key="your-openfda-key",
    ncbi_api_key="your-ncbi-key",
    ncbi_email="you@example.com",
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
| `ncbi_api_key` | `str \| None` | `None` | NCBI API key — raises rate limit from 3 to 10 req/sec |
| `ncbi_email` | `str \| None` | `None` | Email for NCBI requests (recommended by NCBI) |

!!! tip "Where to get API keys"
    - **OpenFDA:** Register at [open.fda.gov/apis/authentication/](https://open.fda.gov/apis/authentication/) — free, instant
    - **NCBI:** Register at [ncbiinsights.ncbi.nlm.nih.gov](https://ncbiinsights.ncbi.nlm.nih.gov/2017/11/02/new-api-keys-for-the-e-utilities/) — free, instant

### Cache

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `cache_enabled` | `bool` | `True` | Enable/disable DuckDB cache globally |
| `cache_dir` | `Path` | `~/.cache/hypokrates` | Directory for the DuckDB cache file |

The cache stores HTTP responses locally with source-specific TTLs (24h by default). This reduces API calls and speeds up repeated queries.

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
)
```
