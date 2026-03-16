# Changelog

## Unreleased

### Sprint 10 — Three New Data Sources (OnSIDES, PharmGKB, Canada Vigilance)

### Fixed
- **PharmGKB parser**: `accession_id` e `guideline_id` vinham como `int` da API mas o Pydantic model esperava `str` — adicionado `str()` no parser
- **DailyMed SPL selection**: `label_events("acetaminophen")` selecionava combo acetaminophen+codeine em vez de standalone — `parse_spl_search()` agora retorna `(singles, combos)` separados e `label_events` tenta singles first (4-pass: single AR → single safety → combo AR → combo safety)

### Added
- **onsides/** module: `onsides_events()`, `onsides_check_event()` — NLP-extracted drug-ADE pairs from 51,460 labels across 4 countries (US/EU/UK/JP) via PubMedBERT (F1=0.935)
  - DuckDB store at `~/.cache/hypokrates/onsides.duckdb` (same pattern as DrugBank/ANVISA)
  - Loads 7 CSVs from OnSIDES ZIP (313MB download): product_label, product_adverse_effect, product_to_rxnorm, vocab_rxnorm_product, vocab_rxnorm_ingredient_to_product, vocab_rxnorm_ingredient, vocab_meddra_adverse_effect
  - Query joins RxNorm ingredient → product → label → adverse effect → MedDRA vocab with confidence scores and country sources
  - `OnSIDESEvent` model: meddra_id, meddra_name, label_section (BW/WP/AR), confidence (pred1), sources, num_sources
  - `OnSIDESResult` model with MetaInfo
  - `check_onsides` parameter on `hypothesis()` and `scan_drug()` (opt-in)
  - `HypothesisResult.onsides_sources` field (list of country codes where ADE found)
  - MCP tools: `onsides_events`, `onsides_check_event`
  - Sync wrapper: `from hypokrates.sync import onsides`
  - Config: `onsides_path: Path | None` in HypokratesConfig
  - `Source.ONSIDES` enum value
  - 25 new tests with golden data

- **pharmgkb/** module: `pgx_annotations()`, `pgx_guidelines()`, `pgx_drug_info()` — pharmacogenomic gene-drug associations and dosing guidelines (CPIC/DPWG) from PharmGKB REST API
  - HTTP client inheriting BaseClient (cache + rate limit at 60/min)
  - Evidence level filtering (1A strongest → 4 weakest)
  - `PharmGKBAnnotation` model: gene_symbol, level_of_evidence, annotation_types, score
  - `PharmGKBGuideline` model: source (CPIC/DPWG/CPNDS/RNPGx), genes, recommendation, summary
  - `PharmGKBResult` model with annotations, guidelines, pharmgkb_id, MetaInfo
  - `check_pharmgkb` parameter on `hypothesis()` and `scan_drug()` (opt-in)
  - `HypothesisResult.pharmacogenomics` field (gene summaries with evidence levels)
  - MCP tools: `pgx_drug_info`, `pgx_annotations`
  - Sync wrapper: `from hypokrates.sync import pharmgkb`
  - `Source.PHARMGKB` enum value, `PHARMGKB_TTL = 7 days`
  - 19 new tests with golden data + respx mocks

- **canada/** module: `canada_signal()`, `canada_top_events()`, `canada_bulk_status()` — Canadian pharmacovigilance database (1965-present, ~738K reports)
  - DuckDB store at `~/.cache/hypokrates/canada_vigilance.duckdb` (same pattern as FAERS Bulk)
  - Parses $-delimited files from bulk download (325MB ZIP): Reports, Report_Drug, Reactions, Drug_Product, Drug_Product_Ingredients
  - PRR calculation with four_counts (same formula as FAERS)
  - `CanadaSignalResult` model: drug_event_count, drug_total, event_total, total_reports, prr, signal_detected
  - `CanadaBulkStatus` model: total_reports, total_drugs, total_reactions, date_range
  - `check_canada` parameter on `hypothesis()` and `scan_drug()` (opt-in)
  - `HypothesisResult.canada_reports`, `HypothesisResult.canada_signal` fields
  - MCP tools: `canada_signal`, `canada_top_events`, `canada_bulk_status`
  - Sync wrapper: `from hypokrates.sync import canada`
  - Config: `canada_bulk_path: Path | None` in HypokratesConfig
  - `Source.CANADA` enum value
  - 22 new tests with golden data

### Previous (Sprint 9)

### Added
- `protective_signal` classification in `hypothesis()` and `scan_drug()` — detects PRR < 1 with CI entirely below 1 (e.g., aspirin + colorectal cancer PRR=0.05). New `HypothesisClassification.PROTECTIVE_SIGNAL` enum value. `CLASSIFICATION_WEIGHTS[PROTECTIVE_SIGNAL]=3.0`
- `no_data` field on `SignalResult` — distinguishes "no FAERS reports for this term" (drug+event=0) from "no signal" (PRR near 1). MCP signal tool shows "NO DATA" and warning when term is absent from FAERS

### Changed
- MeSH ranking: `map_to_mesh()` now boosts shallower (more general) MeSH headings — fixes "arrhythmia" mapping to "Arrhythmia, Sinus" instead of "Arrhythmias, Cardiac"
- DailyMed SPL: combination product penalty increased from -30 to -50 — fixes "acetaminophen" picking codeine combo instead of standalone label
- DailyMed `match_event_in_label()`: new Layer 2.5 (all-words-present in full raw_text) — catches multi-word events split across sections (e.g., "febrile neutropenia" in cisplatin label)
- DailyMed `parse_indications_text()` — extracts INDICATIONS AND USAGE section (LOINC 34067-9) from SPL XML for indication confounding detection
- DailyMed MCP tools: `check_label` and `label_events` now show "drug may be withdrawn" warning when no SPL found
- Co-admin Layer 2 now triggers on `co_admin_flag=True` even without FAERS signal — catches confounding in ondansetron+febrile neutropenia scenarios
- `HypothesisResult.indication_confounding` field — True when event matches known therapeutic indication (static INDICATION_TERMS list)
- `hypothesis()` MCP output shows "⚠ INDICATION CONFOUNDING" warning when event matches indication

### Fixed
- `_build_summary()` no longer says "FAERS signal detected" when `signal_detected=False` (e.g., aspirin+colorectal cancer as `emerging_signal` without FAERS signal now says "No FAERS disproportionality signal, but literature suggests emerging evidence")
- `_build_summary()` for `known_association` without FAERS signal (e.g., label+literature only) now says "No FAERS signal, but well-documented in literature and FDA label"

### Previous (Sprint 8)

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
- **Hypothesis classification without FAERS signal**: `_classify()` now considers literature and label even when FAERS signal is absent. Previously, no FAERS signal always returned `no_signal` regardless of evidence — e.g., CBD + hepatotoxicity (45 papers, FDA black box warning) was classified as `no_signal`. Now: in_label + >5 papers = `known_association`; >5 papers without label = `emerging_signal`; 0 papers = `no_signal` (preserved).
- **Co-admin analysis always runs**: `hypothesis(check_coadmin=True)` now runs Layer 1 (co-suspect profile) even without FAERS signal, returning `verdict="no_signal"`. Previously silently skipped.
- **FAERS brand name normalization**: `resolve_drug_field()` now tries `normalize_drug()` via RxNorm BEFORE falling back to `brand_name.exact` and `medicinalproduct`. Previously, brand names like "Diprivan" matched `brand_name.exact` (1,296 reports = 9% coverage) instead of resolving to "propofol" via `generic_name.exact` (14,143 reports = full coverage). Fixes inconsistent PRR when using brand vs generic names.
- **DailyMed combination product penalty**: `_score_spl_candidate()` now penalizes titles containing " AND ", " WITH ", " / " (-30 points). Fixes acetaminophen picking "ACETAMINOPHEN AND CODEINE PHOSPHATE" label (opioid AEs attributed to acetaminophen).
- **DailyMed systemic vs topical priority**: Increased scoring weights — prescription forms +25 (was +10), topical forms -25 (was -10), `spl_version` capped at 5 to prevent high revision numbers from dominating. Fixes hydrocortisone picking topical cream instead of systemic formulation (missing Cushing's syndrome, osteoporosis, adrenal suppression).
- **Co-suspect salt form exclusion**: `co_suspect_profile()` now excludes drug salt forms (e.g., "ONDANSETRON HYDROCHLORIDE") from co-suspect list when querying "ONDANSETRON". Uses `startswith()` check in both directions.
- **MCP list_tools undercount**: Added 5 missing tools to meta listing: `drugs_by_event`, `co_suspect_profile`, `anvisa_buscar`, `anvisa_genericos`, `anvisa_mapear_nome`. Added "anvisa" to modules list. Tool count: 29 → 34.
- **DailyMed label matching**: `match_event_in_label()` now expands events via MedDRA synonyms before matching. Previously, "anaphylactic shock" would not match "anaphylaxis" in the label, causing `in_label=False` and inflating scan scores 3x (1.5x boost instead of 0.5x penalty). Now uses `expand_event_terms()` for bidirectional synonym matching across 35 MedDRA groups (~120 aliases).
- **DailyMed label matching (fuzzy)**: Added `rapidfuzz` layer 3 matching (`token_sort_ratio >= 85`) — catches reordered words ("hyperthermia malignant" → "malignant hyperthermia"), BrE/AmE spellings (apnoea/apnea), and minor variations (QT/QTc).
- **DailyMed SPL selection**: `label_events()` now fetches up to 10 SPLs and selects the first with safety sections (LOINC codes 34084-4, 34066-1, 34071-1, 43685-7). Previously picked the first SPL which could be a powder/OTC/patch without adverse reactions. Fixes gabapentin, lidocaine, acetaminophen returning 0 events.
- **RxNorm normalization**: `normalize_drug()` now has 3-step fallback: (1) /drugs.json, (2) /rxcui.json + /allrelated.json (resolves SBD → IN), (3) NOME_PT_EN mapping (dipirona→metamizole, paracetamol→acetaminophen). Fixes Diprivan→propofol, Ozempic→semaglutide.
- **FAERS brand→generic**: `resolve_drug_field()` now calls `normalize_drug()` as fallback when no FAERS field matches. Fixes Diprivan (16→236 reports), Ozempic, and other brand names returning near-zero results.
- **FAERS drugs_by_event MedDRA**: `_build_event_search()` now expands events via `expand_event_terms()` — "malignant hyperthermia" also searches "hyperthermia malignant" (and other MedDRA synonyms).
- **signal_timeline limit**: Changed `limit=100` to `limit=1000` in `signal_timeline()` — recovers 2016-2019 data that was being truncated.
- **Trials total_count**: `parse_studies()` now falls back to `len(studies)` when API returns `totalCount=0` with studies present.
- **MedDRA `expand_event_terms()`**: Aliases now expand to full group (canonical + all aliases), not just the alias itself. Affects label matching and FAERS API reaction queries.
- **OPERATIONAL_MEDDRA_TERMS**: Added 4 missing generic terms: `GENERAL PHYSICAL HEALTH DETERIORATION`, `PAIN`, `FALL`, `MALAISE`.
- **MedDRA expansion OpenFDA (CRITICAL)**: `_build_reaction_query()` and `_build_event_search()` used `+` (AND in OpenFDA/Lucene) instead of space (OR). All 38 MedDRA groups returned 0 results in API path — `signal()`, `drugs_by_event()`, and `scan_drug(use_bulk=false)` missed cardiac arrest, anaphylaxis, bradycardia, etc.
- **MedDRA expansion FAERS Bulk (CRITICAL)**: `bulk_signal()` and `bulk_signal_timeline()` passed event term literally without MedDRA expansion. SQL `WHERE pt_upper = $event` → `WHERE pt_upper = ANY($events)`. `four_counts()` now accepts `str | list[str]`.
- **Direction analysis (PS-PRR)**: Was broken for MedDRA-grouped events because `bulk_signal()` didn't expand synonyms — PS-PRR=0 for canonical terms like "ANAPHYLAXIS". Auto-fixed by bulk MedDRA expansion.
- **DrugBank graceful degradation**: `hypothesis(check_drugbank=True)` crashed with `ConfigurationError` when DrugBank XML not configured. Now catches exception and continues without DrugBank data.
- **OpenTargets MedDRA expansion**: `drug_safety_score()` matched event literally — "anaphylaxis" returned None while "anaphylactic shock" returned 2375. Now expands via `expand_event_terms()` and picks highest LRT.
- **INDICATION_TERMS cleanup**: Removed `ANAPHYLAXIS` and `URTICARIA` (adverse events, not indications). Added `ATRIAL FIBRILLATION`, `HEART FAILURE`, `VENTRICULAR TACHYCARDIA` (common cardiac indications that inflate PRR via confounding).
- **OPERATIONAL_MEDDRA_TERMS**: Added `PRODUCT PACKAGING CONFUSION` (was appearing as novel_hypothesis in scans).
- **compare_signals MedDRA grouping**: Auto-detected events now deduplicated by `canonical_term()` — "ANAPHYLACTIC SHOCK" and "ANAPHYLACTIC REACTION" merge into "ANAPHYLAXIS".
- **compare_signals operational filtering**: Auto-detected events now filtered via `OPERATIONAL_MEDDRA_TERMS` — removes "DRUG INEFFECTIVE", "DEATH", etc.
- **Co-admin verdict/warning mismatch**: MCP output showed "⚠ Co-admin confounding likely" even when verdict was "specific". Now conditionally shows appropriate message.
- **DailyMed SPL ranking (Bug #22/#23)**: `parse_spl_search()` now ranks SPL candidates by heuristic score — injection/tablet/capsule forms get +10 bonus, OTC topicals (patch/cream/gel) get -10 penalty, veterinary labels (Covetrus, Dechra, Zoetis, etc.) get -100. Fixes lidocaine returning OTC patch events ("avoid contact with eyes") and ketamine returning veterinary label events ("In the cat, myoclonic jerking").
- **DailyMed SPL selection two-pass**: `label_events()` now selects SPLs in two passes — first prefers SPLs with formal Adverse Reactions section (LOINC 34084-4), then falls back to any safety section. OTC labels typically have only Warnings (34071-1), not Adverse Reactions.
- **DailyMed SPL pagesize**: Increased from 10 to 100 to surface prescription labels for drugs with many OTC formulations (lidocaine: 2,403 SPLs, first 10 were all patches).

### Fixed (6 bugs from MCP stress test #2, 2026-03-16)
- **MedDRA common terms**: Added 7 new groups (cardiac failure, cerebrovascular accident, haemorrhage, pulmonary fibrosis, depression, pyrexia, rash) + expanded 3 existing (hepatotoxicity +3 aliases, myocardial infarction +heart attack, deep vein thrombosis +blood clot). Fixes "heart failure", "stroke", "bleeding", "fever" etc. returning 0 reports silently.
- **hypothesis() graceful degradation**: All optional enrichments (check_label, check_trials, check_opentargets, check_chembl, check_coadmin) now wrapped in try/except — previously only check_drugbank had error handling. Exceptions log a warning and continue with None instead of propagating.
- **DailyMed word-level matching**: Added Layer 1.5 (all-words-present) between substring and fuzzy matching — "pulmonary fibrosis" now matches "pulmonary infiltrates or fibrosis" in label text.
- **MeSH mapping ranking**: `map_to_mesh()` now fetches top 5 UIDs and ranks by similarity (rapidfuzz token_sort_ratio) instead of blindly picking first result. Fixes "lactic acidosis"→MELAS and "arrhythmia"→Anti-Arrhythmia Agents.
- **Bulk status real counts**: `BulkStoreStatus` now includes `total_drug_records` and `total_reac_records` computed from actual DB tables. Previously showed 0 for quarters loaded before metadata tracking was added.
- **DrugBank MCP error message**: `drug_info` and `drug_interactions` MCP tools now catch `HypokratesError` and return friendly message with configuration instructions instead of raw exception.

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
