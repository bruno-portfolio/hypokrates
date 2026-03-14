# Data Sources

hypokrates queries multiple public health databases. Each source has its own rate limits, authentication requirements, and data characteristics.

## Implemented

| Source | Module | Coverage | Rate Limit (no key) | Rate Limit (with key) |
|--------|--------|----------|---------------------|----------------------|
| [OpenFDA/FAERS](faers.md) | `hypokrates.faers` | 20M+ reports (2004–present) | 40 req/min | 240 req/min |
| [NCBI/PubMed](pubmed.md) | `hypokrates.pubmed` | 36M+ citations | 3 req/sec | 10 req/sec |

## Planned

| Source | Description | Status |
|--------|-------------|--------|
| DrugBank | Drug–drug interactions, pharmacology | Planned |
| WHO VigiBase | International adverse event reports | Planned |
| GBD (IHME) | Global Burden of Disease | Planned |
| OpenAlex | Open-access scholarly metadata | Planned |
| ClinicalTrials.gov | Clinical trial registry | Planned |
| DATASUS | Brazilian public health data | Planned |

## Authentication

Both implemented sources work **without API keys** but with reduced rate limits. See [Configuration](../guides/configuration.md) for how to obtain and configure API keys.

## Caching

All HTTP responses are cached in a local DuckDB database with source-specific TTLs:

| Source | Default TTL |
|--------|-------------|
| FAERS | 24 hours |
| PubMed | 24 hours |

Cache can be disabled per-call with `use_cache=False` or globally via `configure(cache_enabled=False)`.
