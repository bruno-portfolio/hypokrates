# hypokrates

**Cross-reference pharmacovigilance data for medical hypothesis generation.**

[![PyPI](https://img.shields.io/pypi/v/hypokrates)](https://pypi.org/project/hypokrates/)
[![Tests](https://img.shields.io/badge/tests-1132%20passing-brightgreen)]()
[![Coverage](https://img.shields.io/badge/coverage-91%25-brightgreen)]()
[![License](https://img.shields.io/badge/license-MIT-blue)](https://github.com/brunoescalhao/hypokrates/blob/main/LICENSE)
[![Python](https://img.shields.io/badge/python-3.11%2B-blue)]()

!!! warning "Alpha — Not for clinical use"
    hypokrates is in active development. Output is for **research and screening only**.
    It does not replace clinical judgment, regulatory review, or established pharmacovigilance processes.

## What is hypokrates?

hypokrates is a Python library that queries public pharmacovigilance databases (FAERS, PubMed), computes disproportionality signals (PRR, ROR, IC), and cross-references the results to classify drug–adverse event pairs into hypothesis categories.

It is designed for researchers, pharmacovigilance professionals, and developers building safety screening tools. All results include full provenance metadata and known limitations — no black boxes.

## Quick Example

=== "Async"

    ```python
    import asyncio
    from hypokrates.cross import api as cross

    async def main():
        result = await cross.hypothesis("propofol", "bradycardia")
        print(result.classification)  # e.g., "known_association"
        print(result.summary)

    asyncio.run(main())
    ```

=== "Sync"

    ```python
    from hypokrates.sync import cross

    result = cross.hypothesis("propofol", "bradycardia")
    print(result.classification)  # e.g., "known_association"
    print(result.summary)
    ```

## Modules

| Module | Description | Key Functions |
|--------|-------------|---------------|
| [`faers`](api/faers.md) | Query FDA Adverse Event Reporting System | `adverse_events()`, `top_events()`, `compare()` |
| [`stats`](api/stats.md) | Disproportionality signal detection | `signal()` |
| [`pubmed`](api/pubmed.md) | Search NCBI/PubMed literature | `count_papers()`, `search_papers()` |
| [`cross`](api/cross.md) | Cross-reference FAERS + PubMed | `hypothesis()` |
| [`scan`](api/scan.md) | Automated drug adverse event scanning | `scan_drug()` |
| [`vocab`](api/vocab.md) | Drug name normalization, MeSH mapping | `normalize_drug()`, `map_to_mesh()` |
| [`evidence`](api/evidence.md) | Evidence provenance blocks | `build_evidence()`, `build_faers_evidence()` |

## Data Sources

| Source | Status | Coverage |
|--------|--------|----------|
| [OpenFDA/FAERS](sources/faers.md) | Implemented | 20M+ reports (2004–present) |
| [FAERS Bulk](sources/faers.md#faers-bulk-quarterly-files) | Implemented | Deduplicated quarterly ASCII files |
| [NCBI/PubMed](sources/pubmed.md) | Implemented | 36M+ citations |
| RxNorm (NLM) | Implemented | Drug name normalization |
| NCBI/MeSH | Implemented | Medical Subject Headings |
| [DailyMed](sources/dailymed.md) | Implemented | FDA drug labels (SPL) |
| [ClinicalTrials.gov](sources/trials.md) | Implemented | 500K+ trials |
| [DrugBank](sources/drugbank.md) | Implemented | 16K+ drugs (XML) |
| [OpenTargets](sources/opentargets.md) | Implemented | FAERS-based LRT scores |
| ChEMBL | Implemented | Mechanism of action, targets |
| [ANVISA](sources/anvisa.md) | Implemented | 46K+ Brazilian drugs |
| WHO VigiBase | Planned | — |
| GBD | Planned | — |
| OpenAlex | Planned | — |
| DATASUS | Planned | — |

## Features

- **Async-first** with sync wrappers — works in scripts, notebooks, and web frameworks
- **DuckDB cache** — automatic caching with configurable TTL, no external services needed
- **Retry with backoff** — resilient HTTP client with per-source rate limiting
- **Typed models** — Pydantic v2 models with full type coverage (mypy strict)
- **Evidence provenance** — every result includes source, query, timestamp, limitations, and disclaimers

## Next Steps

- [Quickstart](quickstart.md) — install and run your first query in 5 minutes
- [API Reference](api/faers.md) — full function signatures and models
- [Concepts](concepts/signal-detection.md) — understand disproportionality analysis
