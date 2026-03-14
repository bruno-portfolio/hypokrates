# Changelog

All notable changes to this project will be documented in this file.

## 0.4.0 (Unreleased)

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
