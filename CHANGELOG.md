# Changelog

## Unreleased

### Added
- Bulk scan: `scan_drug()` now uses FAERS Bulk (deduplicated quarterly files) for event discovery when available
  - `bulk_top_events(drug, role_filter, limit)` — top events from bulk store with dedup + role filter
  - `bulk_drug_total(drug, role_filter)` — total deduplicated cases for a drug
  - `FAERSBulkStore.top_events()`, `FAERSBulkStore.drug_total()` — new DuckDB store methods
  - `primary_suspect_only` parameter on `scan_drug()` — PS-only role filter (requires bulk)
  - `ScanItem.ps_only_prr`, `ScanItem.direction` fields — direction analysis results
  - `ScanResult.bulk_mode`, `ScanResult.role_filter_used` fields — data source metadata
- Direction analysis: `check_direction=True` on `scan_drug()` compares base PRR vs PS-only PRR per signal
  - `"strengthens"` if PS PRR > 1.2x base (pharmacological signal)
  - `"weakens"` if PS PRR < 0.8x base (confounding probable)
  - `DIRECTION_STRENGTHENS_THRESHOLD=1.2`, `DIRECTION_WEAKENS_THRESHOLD=0.8`
- MCP `scan_drug` tool gains `role_filter` param ("ps_only"/"suspect"/"all") and `check_direction`
- MCP output shows data source (API vs Bulk), role filter, PS-PRR, and direction per item
- Co-administration confounding detection (Layer 1 + Layer 2)
  - `co_suspect_profile(drug, event)` — analyzes co-suspect patterns in FAERS reports (median suspects/report, top co-drugs)
  - `coadmin_analysis(drug, event, profile)` — compares drug PRR vs co-administered drugs PRR to determine specificity
  - `check_coadmin` parameter on `hypothesis()` and `scan_drug()` (opt-in)
  - `CoSuspectProfile`, `CoAdminAnalysis`, `CoSignalItem` models
  - Verdict system: `"specific"`, `"co_admin_artifact"`, `"inconclusive"`
  - Scan integration: `coadmin_flag`, `coadmin_detail` on ScanItem, `coadmin_flagged_count` on ScanResult, `CO_ADMIN_MULTIPLIER=0.3` score penalty
  - MCP tool: `co_suspect_profile` for interactive analysis
  - `Limitation.CO_ADMINISTRATION` evidence enum
  - 20 new tests covering both layers
- `drugs_by_event(event)` — reverse lookup FAERS (event → top drugs)
- `hypokrates.anvisa` module — Brazilian drug registry (ANVISA open data)
- `buscar_medicamento()` — search by brand name or active ingredient (accent-insensitive, partial match)
- `buscar_por_substancia()` — search by active ingredient with optional category filter (Genérico/Similar/Referência)
- `listar_apresentacoes()` — list presentations/dosages for a drug
- `mapear_nome()` — bidirectional PT ↔ EN drug name mapping (~95 drugs)
- Auto-download of ANVISA CSV (~5 MB) on first call, with 30-day refresh
- DuckDB store at `~/.cache/hypokrates/anvisa.duckdb` (separate from HTTP cache)
- `AnvisaMedicamento`, `AnvisaSearchResult`, `AnvisaNomeMapping` models (with `image_url` field for future use)
- MCP tools: `anvisa_buscar`, `anvisa_genericos`, `anvisa_mapear_nome`
- Sync wrapper: `from hypokrates.sync import anvisa`
- `Source.ANVISA` enum value
- `anvisa_csv_path` configuration parameter
- 66 new tests (88% coverage)

### Fixed
- **DailyMed label matching**: `match_event_in_label()` now expands events via MedDRA synonyms before matching. Previously, "anaphylactic shock" would not match "anaphylaxis" in the label, causing `in_label=False` and inflating scan scores 3x (1.5x boost instead of 0.5x penalty). Now uses `expand_event_terms()` for bidirectional synonym matching across 35 MedDRA groups (~120 aliases).
- **MedDRA `expand_event_terms()`**: Aliases now expand to full group (canonical + all aliases), not just the alias itself. Affects label matching and FAERS API reaction queries.

### Changed
- IC upgraded from simplified to BCPNN (Norén et al. 2006) with Jeffreys prior (alpha=0.5) — resolves small-numbers instability

## [0.4.0] - 2026-03-14

### Added
- Sprint 4: scan/ + vocab/ modules
- `hp.scan.scan_drug()` — automated scan of top FAERS adverse events with parallel hypothesis generation
- `ScanItem`, `ScanResult` models with scoring and ranking
- Configurable concurrency via `asyncio.Semaphore`, progress callback (`on_progress`)
- `hp.vocab.normalize_drug()` — normalize drug names via RxNorm (brand → generic)
- `hp.vocab.map_to_mesh()` — map medical terms to MeSH headings via NCBI E-utilities
- `DrugNormResult`, `MeSHResult` models
- `RxNormClient` with cache/retry/rate-limit (Source.RXNORM, 120/min)
- `MeSHClient` sharing NCBI rate limit with PubMed (Source.MESH for cache, Source.PUBMED for rate)
- RxNorm/MeSH parsers (`parse_rxnorm_drugs`, `parse_mesh_search`, `parse_mesh_descriptor`)
- `Source.RXNORM`, `Source.MESH` enum values, `RXNORM_BASE_URL`
- Cache TTL 90 days for vocab sources (RxNorm, MeSH)
- Sync wrappers for scan and vocab (`from hypokrates.sync import scan, vocab`)
- MCP server with 12 tools (faers:3, stats:1, pubmed:2, cross:1, scan:1, vocab:2, meta:2)
- Golden data for vocab tests (RxNorm, MeSH)
- 41 new tests (403 → 444 total)

### Changed
- `CLASSIFICATION_WEIGHTS` uses `HypothesisClassification` enum keys instead of strings
- `vocab/constants.py` imports NCBI constants from `pubmed/constants.py` (deduplication)

## [0.3.0] - 2026-03-14

### Added
- Sprint 3: PubMed client + hypothesis cross-referencing
- `hp.pubmed.count_papers()` — count PubMed papers for a drug-event pair (1 request)
- `hp.pubmed.search_papers()` — search with article metadata (2 requests: ESearch + ESummary)
- `PubMedClient` with search_count, search_ids, fetch_summaries (cache/retry/rate-limit)
- `PubMedArticle`, `PubMedSearchResult` models
- `build_search_term()` with free text and MeSH qualifier support
- `hp.cross.hypothesis()` — cross-reference FAERS signal + PubMed literature
- `HypothesisClassification` (novel_hypothesis, emerging_signal, known_association, no_signal)
- `HypothesisResult` with configurable thresholds (novel_max, emerging_max)
- Concurrent FAERS + PubMed requests via `asyncio.gather()`
- Sync wrappers for pubmed and cross (`from hypokrates.sync import pubmed, cross`)
- NCBI config fields (ncbi_api_key, ncbi_email) in HypokratesConfig
- PubMed rate limiting (180/min without key, 600/min with key)
- PubMed cache TTL policy
- Golden data for PubMed tests (esearch, esummary, count_only, no_results)
- 60 new tests (343 → 403 total, 91% coverage)

## [0.2.0] - 2026-03-14

### Added
- Sprint 2: Signal detection, evidence blocks, contracts
- `hp.stats.signal()` — disproportionality analysis (PRR, ROR, IC simplified) for drug-event pairs
- `ContingencyTable`, `DisproportionalityResult`, `SignalResult` models
- `EvidenceBlock` with full provenance (source, query, limitations, disclaimer)
- `Limitation` enum (7 known data source limitations)
- `build_evidence()`, `build_faers_evidence()` builders
- `SignalDetector`, `EvidenceProvider` Protocol contracts (runtime_checkable)
- `FAERSClient.fetch_total()` for count queries
- Sync wrapper for stats (`from hypokrates.sync import stats`)
- Golden data for signal detection tests

### Fixed
- Removed misplaced root scaffold directories (datasus/, drugbank/, etc.) — they were outside the Python package

## [0.1.0] - 2026-03-14

### Added
- Sprint 1: FAERS foundation
- OpenFDA/FAERS client with pagination
- DuckDB cache layer (thread-safe singleton)
- HTTP retry with exponential backoff
- Per-source rate limiting
- Domain models (Drug, AdverseEvent, FAERSReport)
- Sync wrapper (`hypokrates.sync`)
- `hp.faers.adverse_events()` — query adverse events
- `hp.faers.top_events()` — top reported events for a drug
- `hp.faers.compare()` — compare drugs by outcome
