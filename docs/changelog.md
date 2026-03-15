# Changelog

All notable changes to this project will be documented in this file.

## Unreleased

### Sprint 8 — Bulk Scan, Label Match Fix, Direction Analysis

- **faers_bulk/**: `bulk_top_events()`, `bulk_drug_total()` — event discovery via deduplicated bulk store with role filter (PS_ONLY, SUSPECT, ALL)
- **faers_bulk/store.py**: `FAERSBulkStore.top_events()`, `FAERSBulkStore.drug_total()` — new SQL methods
- **scan/**: `scan_drug()` now uses FAERS Bulk for event discovery when available (dual-mode: bulk vs API)
- **scan/**: `primary_suspect_only` param — PS-only role filter for event discovery (bulk only, falls back to suspect_only without bulk)
- **scan/**: `check_direction` param — compares base PRR vs PS-only PRR per signal
  - `"strengthens"` if PS PRR > 1.2x base (pharmacological signal)
  - `"weakens"` if PS PRR < 0.8x base (confounding probable)
- **scan/models.py**: `ScanItem.ps_only_prr`, `ScanItem.direction`, `ScanResult.bulk_mode`, `ScanResult.role_filter_used`
- **dailymed/parser.py**: `match_event_in_label()` now uses MedDRA synonyms via `expand_event_terms()` — fixes false negatives for clinically equivalent terms (e.g., "anaphylactic shock" now matches "anaphylaxis" in label)
- **vocab/meddra.py**: `expand_event_terms()` now expands aliases to full group (canonical + all aliases)
- **MCP**: `scan_drug` gains `role_filter` ("ps_only"/"suspect"/"all") and `check_direction` params; output shows data source, role filter, PS-PRR, and direction
- 29 new tests (1105+ total)

### Sprint 7 — Suspect-Only, Operational Filter, Over-Fetch, Co-Admin, ANVISA

### Changed

- **stats:** IC upgraded from simplified to BCPNN (Norén et al. 2006) with Jeffreys prior — resolves small-numbers instability

### Fixes

- **DailyMed:** Fixed HTTP 406 error when fetching SPL XML — removed invalid `Accept: application/xml` header (server returns XML based on URL extension)
- **ClinicalTrials.gov:** Fixed HTTP 403 from Cloudflare TLS fingerprinting — TrialsClient now uses `curl_cffi` (optional dep) with Chrome impersonation, falls back to httpx with warning
- Added `curl_cffi` as optional dependency (`pip install hypokrates[trials]`)

### Sprint 6 — MedDRA, DrugBank, OpenTargets

- **vocab/meddra.py**: MedDRA grouping of synonymous adverse event terms (30 groups, static dict, no license required)
- **drugbank/** module: `drug_info()`, `drug_interactions()` — offline DrugBank XML parser with DuckDB store
- DrugBank parser uses `iterparse` + `elem.clear()` for streaming (~175MB XML)
- DrugBank data stored in separate DuckDB (`~/.cache/hypokrates/drugbank.duckdb`)
- **opentargets/** module: `drug_adverse_events()`, `drug_safety_score()` — FAERS-based LRT scores via GraphQL
- OpenTargets resolves drug name to ChEMBL ID via search, then fetches adverse events
- **scan/**: `group_events=True` by default (MedDRA grouping), `check_drugbank`/`check_opentargets` opt-in
- ScanItem gains `grouped_terms`, `mechanism`, `ot_llr`, `groups_applied`, `cyp_enzymes`
- **cross/**: `check_drugbank`/`check_opentargets` opt-in, HypothesisResult gains `mechanism`, `interactions`, `enzymes`, `ot_llr`
- Config gains `drugbank_path` parameter
- MCP: 19 tools registered (+drugbank:2, +opentargets:2)
- 673 total tests

### Sprint 5 — DailyMed, ClinicalTrials.gov, ChEMBL

- **dailymed/** module: `label_events()`, `check_label()` — FDA drug label parsing via DailyMed REST API
- SPL XML parsing extracts Adverse Reactions section (LOINC 34084-4)
- **trials/** module: `search_trials()` — ClinicalTrials.gov v2 API integration
- **chembl/** module: `drug_mechanism()` — mechanism of action, targets, and metabolizing enzymes via ChEMBL REST API (free, no API key)
- **scan/**: `check_label`/`check_trials`/`check_chembl` opt-in flags
- **cross/**: `check_label`/`check_trials`/`check_chembl` opt-in, label cache for scan efficiency
- `Source.DAILYMED`, `Source.TRIALS`, `Source.CHEMBL` added to enum
- Cache TTLs: DailyMed 30 days, Trials 24h, ChEMBL 7 days
- DailyMed rate: 60/min, Trials rate: 50/min
- retry_request() gains optional `headers` parameter
- MCP: tools for dailymed (2), trials (1), chembl (2)

### Sprint 4 — Scan & Vocab

- **scan/** module: `scan_drug()` — automated scanning of top FAERS adverse events with parallel hypothesis generation
- `ScanItem`, `ScanResult` models with scoring and ranking
- Configurable concurrency via `asyncio.Semaphore`, progress callback
- **vocab/** module: `normalize_drug()` (RxNorm), `map_to_mesh()` (NCBI MeSH)
- `RxNormClient`, `MeSHClient` with cache/retry/rate-limit
- `Source.RXNORM`, `Source.MESH`, cache TTL 90 days
- MCP server updated to 12 tools (+scan_drug, +normalize_drug, +map_to_mesh)
- 41 new tests (403 -> 444 total)

### Sprint 3 — Cross-Reference & MCP

- **cross/** module: `hypothesis()` — cross-reference FAERS + PubMed, classify into 4 categories
- **pubmed/** module: `count_papers()`, `search_papers()` — NCBI E-utilities integration
- **evidence/** module: `build_evidence()`, `build_faers_evidence()` — provenance blocks with limitations
- **MCP server** (hypokrates-mcp): 9 tools registered (faers:3, stats:1, pubmed:2, cross:1, meta:2)
- Sync wrappers for all modules (`hypokrates.sync`)

### Sprint 2 — Signal Detection

- **stats/** module: `signal()` — PRR, ROR, IC (simplified) disproportionality measures
- Contingency table construction from FAERS marginal counts
- Signal detection heuristic (>= 2/3 significant measures)

### Sprint 1 — FAERS Foundation

- **faers/** module: `adverse_events()`, `top_events()`, `compare()`
- OpenFDA FAERS client with retry and rate limiting
- DuckDB cache (thread-safe singleton) with TTL-based eviction
- HTTP retry with exponential backoff
- Per-source rate limiter
- Configuration singleton (`configure()`, `get_config()`)
- Exception hierarchy (7 exception types)
- Pydantic v2 models with full type coverage
- mypy strict, ruff clean
