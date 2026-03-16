# Changelog

All notable changes to this project will be documented in this file.

## Unreleased

### Sprint 9 — Signal Quality, Protective Detection, New Sources (in progress)

- **cross/models.py**: `HypothesisClassification.PROTECTIVE_SIGNAL` — new enum value for PRR < 1 with CI entirely below 1 (e.g., aspirin + colorectal cancer)
- **cross/api.py**: `_classify()` now receives `prr`, `prr_ci_upper`, `drug_event_count` to detect protective associations
- **cross/api.py**: `_build_summary()` fix — no longer says "FAERS signal detected" when `signal_detected=False` (emerging/known without FAERS signal)
- **stats/models.py**: `SignalResult.no_data` field — True when drug+event=0 (term absent from FAERS)
- **stats/api.py**: sets `no_data=True` when `drug_event_count == 0`
- **mcp/tools/stats.py**: signal tool shows "NO DATA" + warning when term absent from FAERS
- **scan/constants.py**: `CLASSIFICATION_WEIGHTS[PROTECTIVE_SIGNAL] = 3.0`
- **vocab/api.py**: `map_to_mesh()` depth bonus for shallower MeSH headings (fixes arrhythmia → "Arrhythmias, Cardiac")
- **dailymed/parser.py**: combo penalty -30 → -50 (fixes acetaminophen picking codeine combo)
- **dailymed/parser.py**: `match_event_in_label()` Layer 2.5 — all-words-present in full raw_text (fixes cisplatin + febrile neutropenia)
- **dailymed/parser.py**: `parse_indications_text()` — extracts INDICATIONS AND USAGE (LOINC 34067-9) for indication confounding
- **dailymed/constants.py**: `INDICATIONS_LOINC = "34067-9"`
- **cross/models.py**: `HypothesisResult.indication_confounding` field
- **cross/api.py**: indication confounding detection via `is_indication_term()` — flags events matching known therapeutic indications
- **cross/api.py**: co-admin Layer 2 now triggers on `co_admin_flag=True` (not just `signal_detected`)
- **mcp/tools/cross.py**: `hypothesis` shows "⚠ INDICATION CONFOUNDING" warning
- **mcp/tools/dailymed.py**: `check_label` and `label_events` show "drug may be withdrawn" when no SPL found

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
- 50+ new tests (1142 total)

#### Bug Fixes (7 bugs from MCP stress test session, 2026-03-15)

- **Hypothesis classification without FAERS signal**: `_classify()` now considers literature and label even when FAERS signal is absent — CBD + hepatotoxicity (45 papers, black box warning) was `no_signal`, now correctly `known_association`
- **FAERS brand name normalization**: `resolve_drug_field()` now normalizes via RxNorm BEFORE falling back to `brand_name.exact`. Diprivan was getting 9% of propofol's reports.
- **DailyMed combination product penalty**: `_score_spl_candidate()` now penalizes titles with " AND "/" WITH "/" / " (-30). Fixes acetaminophen picking codeine combination label.
- **DailyMed systemic vs topical priority**: Prescription +25 (was +10), topical -25 (was -10), spl_version capped at 5. Fixes hydrocortisone picking cream instead of systemic.
- **Co-admin analysis always runs**: `hypothesis(check_coadmin=True)` now runs Layer 1 even without FAERS signal.
- **Co-suspect salt form exclusion**: `co_suspect_profile()` excludes drug salt forms (e.g., ONDANSETRON HYDROCHLORIDE) from co-suspect list.
- **MCP list_tools**: Added 5 missing tools (drugs_by_event, co_suspect_profile, anvisa×3). Tool count 29→34.

#### Bug Fixes (10 bugs from bug hunting session)

- **DailyMed label matching (fuzzy)**: Added `rapidfuzz` layer 3 matching (`token_sort_ratio >= 85`) — catches reordered words, BrE/AmE spellings (apnoea/apnea), and minor variations
- **DailyMed SPL selection**: `label_events()` now fetches 10 SPLs and picks first with safety sections — fixes powder/OTC/patch SPLs returning 0 events
- **RxNorm normalization**: 3-step fallback: /drugs.json → /rxcui+allrelated (SBD→IN) → NOME_PT_EN (dipirona→metamizole)
- **FAERS brand→generic**: `resolve_drug_field()` tries `normalize_drug()` as fallback for brand names
- **FAERS drugs_by_event**: `_build_event_search()` now expands MedDRA synonyms
- **signal_timeline**: `limit=100` → `limit=1000` (recovers 2016-2019 data)
- **Trials total_count**: Fallback to `len(studies)` when API returns `totalCount=0`
- **OPERATIONAL_MEDDRA_TERMS**: +4 generic terms (GENERAL PHYSICAL HEALTH DETERIORATION, PAIN, FALL, MALAISE)
- **New dependency**: `rapidfuzz>=3.6,<4`

#### Bug Fixes (6 bugs from MCP stress test #2, 2026-03-16)

- **MedDRA common terms**: +7 groups (cardiac failure, stroke, haemorrhage, pulmonary fibrosis, depression, pyrexia, rash) +6 aliases in 3 existing groups. "heart failure", "stroke", "bleeding", "fever" now expand correctly.
- **hypothesis() graceful degradation**: check_label, check_trials, check_opentargets, check_chembl, check_coadmin now catch exceptions and degrade (previously only check_drugbank had try/except).
- **DailyMed word-level matching**: Layer 1.5 (all-words-present) — "pulmonary fibrosis" matches "pulmonary infiltrates or fibrosis".
- **MeSH ranking**: `map_to_mesh()` ranks top 5 UIDs by similarity. Fixes "lactic acidosis"→MELAS, "arrhythmia"→Anti-Arrhythmia Agents.
- **Bulk status**: `BulkStoreStatus` gains `total_drug_records`, `total_reac_records` (real counts from DB).
- **DrugBank MCP**: Friendly error message with config instructions instead of raw exception.

#### Bug Fixes (11 bugs from MCP dogfooding session)

- **MedDRA expansion OpenFDA (CRITICAL)**: `_build_reaction_query()` and `_build_event_search()` used `+` (AND) instead of space (OR). All 38 MedDRA groups returned 0 via API path.
- **MedDRA expansion FAERS Bulk (CRITICAL)**: `bulk_signal()` and `bulk_signal_timeline()` didn't expand MedDRA. SQL `= $event` → `= ANY($events)`. `four_counts()` accepts `str | list[str]`.
- **Direction analysis (PS-PRR)**: Broken for MedDRA groups — PS-PRR=0 for canonical terms. Auto-fixed by bulk expansion.
- **DrugBank graceful degradation**: `hypothesis(check_drugbank=True)` crashed without DrugBank XML. Now catches and continues.
- **OpenTargets MedDRA**: `drug_safety_score()` matched literally — "anaphylaxis" → None. Now expands via MedDRA.
- **INDICATION_TERMS**: Removed ANAPHYLAXIS, URTICARIA (AEs). Added ATRIAL FIBRILLATION, HEART FAILURE, VENTRICULAR TACHYCARDIA.
- **OPERATIONAL_MEDDRA_TERMS**: +PRODUCT PACKAGING CONFUSION.
- **compare_signals**: Auto-detected events now deduplicated by MedDRA canonical and filtered for operational terms.
- **Co-admin warning**: MCP no longer shows "confounding likely" when verdict is "specific".

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
