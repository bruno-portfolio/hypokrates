# Data Sources

hypokrates queries multiple public health databases. Each source has its own rate limits, authentication requirements, and data characteristics.

## Implemented

| Source | Module | Coverage | Rate Limit (no key) | Rate Limit (with key) |
|--------|--------|----------|---------------------|----------------------|
| [OpenFDA/FAERS](faers.md) | `hypokrates.faers` | 20M+ reports (2004-present) | 40 req/min | 240 req/min |
| [NCBI/PubMed](pubmed.md) | `hypokrates.pubmed` | 36M+ citations | 180 req/min | 600 req/min |
| RxNorm | `hypokrates.vocab` | Drug name normalization | 120 req/min | - |
| MeSH | `hypokrates.vocab` | MeSH term mapping | Shared with PubMed | Shared with PubMed |
| [DailyMed](dailymed.md) | `hypokrates.dailymed` | FDA drug labels (SPL) | 60 req/min | - |
| [ClinicalTrials.gov](trials.md) | `hypokrates.trials` | 500K+ trials | 50 req/min | - |
| [DrugBank](drugbank.md) | `hypokrates.drugbank` | 16K+ drugs (XML) | Local (offline) | - |
| [OpenTargets](opentargets.md) | `hypokrates.opentargets` | FAERS-based LRT scores | 30 req/min | - |
| ChEMBL | `hypokrates.chembl` | Mechanism of action, targets | 30 req/min | - |

## Planned

| Source | Description | Status |
|--------|-------------|--------|
| WHO VigiBase | International adverse event reports | Planned |
| GBD (IHME) | Global Burden of Disease | Planned |
| OpenAlex | Open-access scholarly metadata | Planned |
| DATASUS | Brazilian public health data | Planned |

## Authentication

FAERS and PubMed work **without API keys** but with reduced rate limits. RxNorm, MeSH, DailyMed, ClinicalTrials.gov, OpenTargets, and ChEMBL are fully open APIs with no authentication required.

DrugBank requires a local XML file (free academic license). See [Configuration](../guides/configuration.md) for details.

## Caching

All HTTP responses are cached in a local DuckDB database with source-specific TTLs:

| Source | Default TTL |
|--------|-------------|
| FAERS | 24 hours |
| PubMed | 24 hours |
| RxNorm / MeSH | 90 days |
| DailyMed | 30 days |
| ClinicalTrials.gov | 24 hours |
| OpenTargets | 7 days |
| ChEMBL | 7 days |

DrugBank uses a separate local DuckDB store (`~/.cache/hypokrates/drugbank.duckdb`) — it is not part of the HTTP cache.

Cache can be disabled per-call with `use_cache=False` or globally via `configure(cache_enabled=False)`.

## Special Requirements

### ClinicalTrials.gov — TLS Fingerprinting

ClinicalTrials.gov uses Cloudflare bot protection that blocks standard Python HTTP clients (httpx). hypokrates automatically uses `curl_cffi` when installed to bypass this:

```bash
pip install hypokrates[trials]
# or directly:
pip install curl_cffi
```

Without `curl_cffi`, requests to ClinicalTrials.gov will likely fail with HTTP 403. A warning is logged when falling back to httpx.
