# hypokrates

[![PyPI version](https://img.shields.io/pypi/v/hypokrates)](https://pypi.org/project/hypokrates/)
[![Python](https://img.shields.io/pypi/pyversions/hypokrates)](https://pypi.org/project/hypokrates/)
[![License: AGPL v3](https://img.shields.io/badge/License-AGPL_v3-blue.svg)](https://www.gnu.org/licenses/agpl-3.0)
[![Tests](https://img.shields.io/badge/tests-1349_passing-brightgreen)]()
[![mypy](https://img.shields.io/badge/type_checked-mypy_strict-blue)]()
[![MCP](https://img.shields.io/badge/MCP-44_tools-purple)]()

> Democratizing pharmacovigilance through open public health data.

**hypokrates** is an open-source Python library that normalizes and cross-references 15 global pharmacovigilance and drug safety databases, exposing them via [MCP](https://modelcontextprotocol.io/) so that any person with access to an LLM can generate medical hypotheses.

*Hippocrates observed a few patients. Today we can observe millions. What's missing is the tool to ask better questions.*

The name comes from the original Greek spelling of Hippocrates (*Hippokrates*) — who broke the model of his era by making medical knowledge open instead of guarded by temple priests. The "hypo" prefix also evokes "hypothesis". Public health data collected with public money, normalized and cross-referenced in an open library, so any doctor in the world can generate hypotheses that save lives.

## The problem

Medical knowledge discovery has a bottleneck: **hypothesis generation**.

Tools like OpenEvidence and PubMed solve literature search — finding what has been studied. But they cannot find what **has not been studied yet**. Signals that exist in pharmacovigilance data (20M+ adverse event reports across 3 countries), molecular mechanism databases, and drug labels — but that no one has cross-referenced because the data lives in silos with different formats, vocabularies, and access patterns.

**hypokrates** cross-references FAERS + JADER + Canada Vigilance + PubMed + DailyMed + DrugBank + OpenTargets + ChEMBL + OnSIDES + PharmGKB + ClinicalTrials.gov + ANVISA — and returns a structured hypothesis with evidence level, in seconds.

## Install

```bash
pip install hypokrates

# Optional extras
pip install hypokrates[trials]   # ClinicalTrials.gov (Cloudflare bypass via curl_cffi)
pip install hypokrates[mcp]      # MCP server (typer + mcp)
```

## Quick start

```python
from hypokrates.config import configure

# Optional: API keys raise rate limits
configure(
    openfda_api_key="your-key",     # 40 -> 240 req/min
    ncbi_api_key="your-key",        # 180 -> 600 req/min
    ncbi_email="you@example.com",
)
```

### Signal detection

Disproportionality analysis (PRR, ROR, IC, EBGM) for any drug-event pair:

```python
from hypokrates.sync import stats

result = stats.signal("sugammadex", "bradycardia")
print(f"PRR: {result.prr.value:.2f}")
print(f"Signal: {result.signal_detected}")  # >= 2/3 measures significant
```

### Hypothesis generation

Cross-reference FAERS signal + PubMed + up to 10 optional sources:

```python
from hypokrates.sync import cross

result = cross.hypothesis(
    "sugammadex", "bradycardia",
    check_label=True,        # DailyMed FDA label
    check_trials=True,       # ClinicalTrials.gov
    check_chembl=True,       # ChEMBL mechanism
    check_opentargets=True,  # OpenTargets LRT score
    check_canada=True,       # Canada Vigilance cross-validation
    check_jader=True,        # JADER (Japan) cross-validation
)
print(result.classification)  # novel_hypothesis | emerging_signal | known_association | no_signal
print(result.summary)
```

### Automated drug scanning

Scan top adverse events with parallel hypothesis generation:

```python
from hypokrates.sync import scan

result = scan.scan_drug(
    "sugammadex",
    top_n=15,
    check_labels=True,
    check_chembl=True,
    primary_suspect_only=True,  # PS-only role filter (bulk data)
    check_direction=True,       # base PRR vs PS-only comparison
)
for item in result.items:
    print(f"#{item.rank} {item.event}: {item.classification.value} (score={item.score:.1f})")
```

## Data sources

15 sources across 3 countries, all publicly accessible:

| Source | Module | Coverage | Auth |
|--------|--------|----------|------|
| OpenFDA/FAERS | `faers` | USA, 20M+ reports | Optional API key |
| FAERS Bulk | `faers_bulk` | USA, deduplicated | Local quarterly ZIPs |
| Canada Vigilance | `canada` | Canada, 738K+ reports | Local bulk download |
| JADER (PMDA) | `jader` | Japan, 1M+ reports | Local CSVs (free) |
| PubMed | `pubmed` | Global, 36M+ papers | Optional API key |
| DailyMed | `dailymed` | USA FDA labels | None |
| ClinicalTrials.gov | `trials` | Global | None (needs curl_cffi) |
| DrugBank | `drugbank` | Global | Local XML (free academic) |
| OpenTargets | `opentargets` | Global | None |
| ChEMBL | `chembl` | Global | None |
| OnSIDES | `onsides` | US/EU/UK/JP labels | Local CSVs (free) |
| PharmGKB | `pharmgkb` | Global pharmacogenomics | None |
| ANVISA | `anvisa` | Brazil drug registry | None (auto-download) |
| RxNorm | `vocab` | Drug name normalization | None |
| MeSH | `vocab` | Medical term mapping | None |

### Demographic stratification

FAERS Bulk and Canada Vigilance support filtering by sex and age group:

```python
from hypokrates.faers_bulk.models import StrataFilter
from hypokrates.sync import faers_bulk

result = faers_bulk.bulk_signal(
    "rocuronium", "anaphylactic shock",
    strata=StrataFilter(sex="F", age_group="65+"),
)
```

### Cross-country validation

The same drug-event pair checked across USA, Canada, and Japan:

```python
from hypokrates.sync import stats, canada, jader

usa = stats.signal("rocuronium", "anaphylactic shock")
can = canada.canada_signal("rocuronium", "anaphylactic shock")
jpn = jader.jader_signal("rocuronium", "anaphylactic shock")
```

## MCP Server

44 tools available for LLM integration via [Model Context Protocol](https://modelcontextprotocol.io/):

```bash
python -m hypokrates.mcp
```

Configure in Claude Desktop, Cursor, or any MCP client:

```json
{
  "mcpServers": {
    "hypokrates": {
      "type": "stdio",
      "command": "python",
      "args": ["-m", "hypokrates.mcp"],
      "env": {
        "OPENFDA_API_KEY": "your-key",
        "NCBI_API_KEY": "your-key",
        "NCBI_EMAIL": "you@example.com",
        "DRUGBANK_PATH": "/path/to/drugbank.xml",
        "ONSIDES_PATH": "/path/to/onsides/csvs/",
        "CANADA_BULK_PATH": "/path/to/canada/extracted/",
        "JADER_BULK_PATH": "/path/to/jader/csvs/",
        "FAERS_BULK_DIR": "/path/to/faers/quarterly/"
      }
    }
  }
}
```

**Core tools:** `signal`, `hypothesis`, `scan_drug`, `compare_signals`, `compare_class`

**Source tools:** `adverse_events`, `top_events`, `drugs_by_event`, `search_papers`, `label_events`, `check_label`, `search_trials`, `drug_info`, `drug_interactions`, `drug_mechanism`, `drug_adverse_events`, `drug_safety_score`, `onsides_events`, `pgx_annotations`, `normalize_drug`, `map_to_mesh`

**Bulk tools:** `faers_bulk_signal`, `faers_bulk_load`, `canada_signal`, `canada_top_events`, `jader_signal`, `jader_top_events`

## Architecture

```
hypokrates/
├── faers/          # OpenFDA FAERS API (adverse events, co-suspect detection)
├── faers_bulk/     # FAERS quarterly ASCII (dedup, role filter, strata)
├── stats/          # Disproportionality measures (PRR, ROR, IC, EBGM)
├── cross/          # Hypothesis generation (signal + literature + enrichments)
├── scan/           # Automated drug scanning with scoring
├── evidence/       # Evidence blocks with provenance and limitations
├── pubmed/         # PubMed/NCBI E-utilities
├── vocab/          # RxNorm normalization + MedDRA synonym grouping
├── dailymed/       # FDA label parsing (SPL XML)
├── trials/         # ClinicalTrials.gov (curl_cffi for Cloudflare)
├── drugbank/       # DrugBank XML (mechanism, interactions, enzymes)
├── opentargets/    # OpenTargets Platform (GraphQL, LRT scores)
├── chembl/         # ChEMBL (mechanism, targets, metabolism)
├── onsides/        # OnSIDES international labels (NLP-extracted)
├── pharmgkb/       # PharmGKB pharmacogenomics (CPIC/DPWG guidelines)
├── canada/         # Canada Vigilance (cross-country validation)
├── jader/          # JADER/PMDA Japan (cross-country, JP→EN translation)
├── anvisa/         # ANVISA Brazil (drug registry, PT↔EN mapping)
├── cache/          # DuckDB HTTP cache (thread-safe singleton)
├── http/           # BaseClient with retry, rate limiting, auth
└── mcp/            # MCP server (44 tools)
```

**Async-first** with sync wrappers. DuckDB for cache and bulk stores. Pydantic 2 for all models. mypy strict. 1349 tests.

## Who is this for

- The anesthesiologist who saw a pattern in patients and wants to know if it's real
- The researcher at a public university without a bioinformatics team
- The resident who disagrees with a protocol and wants data to support their case
- The doctor in rural Brazil who can't access institutional research infrastructure
- Any medical professional with access to an LLM who wants to generate evidence-based hypotheses

## Important disclaimers

- **Not for clinical use.** hypokrates generates hypotheses, not diagnoses.
- **PRR is not absolute risk.** Disproportionality measures detect reporting patterns, not causation.
- **FAERS is voluntary reporting.** Underreporting is systematic. Absence of signal does not mean absence of risk.
- **Cross-country comparison requires caution.** Different reporting cultures, populations, and healthcare systems.
- Every output includes explicit limitations and confidence levels.

## Status

**Alpha** (v0.7.0) — 1349 tests, mypy strict, ruff clean. Under active development.

## License

[AGPL-3.0-only](LICENSE) — Public data, public code, public benefit.

---

*"First, do no harm." — Hippocratic Oath*

*"First, make the data accessible." — hypokrates*

<!-- mcp-name: io.github.bruno-portfolio/hypokrates -->
