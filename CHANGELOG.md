# Changelog

## Unreleased

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
