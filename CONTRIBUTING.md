# Contributing

Thanks for your interest in contributing to hypokrates! This guide covers everything you need to know.

## How to contribute

### Report bugs

Open an [issue](https://github.com/brunoescalhao/hypokrates/issues) with:
- hypokrates and Python version
- Minimal code that reproduces the problem
- Full output/traceback
- Expected vs actual behavior

### Suggest features

Open an issue with the `enhancement` label. Describe the use case, not just the solution.

### Pull Requests

1. Fork the repository
2. Create a branch: `git checkout -b feat/my-feature`
3. Implement with tests
4. Verify everything passes (see below)
5. Open a PR describing what changed and why

## Development setup

```bash
# Clone
git clone https://github.com/brunoescalhao/hypokrates.git
cd hypokrates

# Virtualenv
python -m venv .venv
source .venv/bin/activate  # Linux/Mac
.venv\Scripts\activate     # Windows

# Install in dev mode
pip install -e ".[dev]"

# Pre-commit hooks
pre-commit install
pre-commit install --hook-type pre-push
```

## Verification

All checks must pass before opening a PR:

```bash
# Tests
pytest tests/ -v --timeout=30

# Linting
ruff check hypokrates/ tests/
ruff format --check hypokrates/ tests/

# Type checking (strict)
mypy hypokrates/

# Coverage (gate: 85%)
pytest tests/ --cov=hypokrates --cov-fail-under=85
```

## Code standards

### Type hints

- mypy strict — zero `any`
- `unknown` + type guards when the type is unknown
- Type-only imports: `from __future__ import annotations` + `TYPE_CHECKING`

### Naming conventions

- Variables/functions: `snake_case`
- Classes/Types: `PascalCase`
- Constants: `UPPER_SNAKE_CASE`
- Public API in English
- Medical domain may use Portuguese in comments

### Docstrings

Google convention. Every public function needs a docstring.

```python
def compute_prr(table: ContingencyTable) -> DisproportionalityResult:
    """PRR = (a/(a+b)) / (c/(c+d)), CI via Rothman-Greenland.

    Args:
        table: 2x2 contingency table.

    Returns:
        DisproportionalityResult with PRR, 95% CI and significance flag.
    """
```

### Imports

```python
from __future__ import annotations

# stdlib
import math
from typing import TYPE_CHECKING

# third-party
from pydantic import BaseModel

# local
from hypokrates.models import MetaInfo

if TYPE_CHECKING:
    from collections.abc import Sequence
```

### Error handling

- Never use empty catch or catch with just `console.log`
- Log with context: operation, relevant IDs, error message
- User-facing messages: generic. Log messages: specific

### Tests

- Every new module needs tests
- Golden data for API responses (JSON fixtures in `tests/golden_data/`)
- Mock HTTP via `respx` — never call real APIs in unit tests
- Integration tests marked with `@pytest.mark.integration`

## Project structure

```
hypokrates/
├── config.py          # HypokratesConfig singleton
├── constants.py       # Source enum, URLs, settings
├── exceptions.py      # HypokratesError hierarchy
├── models.py          # Drug, AdverseEvent, MetaInfo
├── sync.py            # Synchronous wrappers
├── faers/             # OpenFDA/FAERS (client, parser, models)
├── faers_bulk/        # FAERS quarterly ASCII (dedup, role filter, strata)
├── stats/             # PRR, ROR, IC, EBGM — signal detection
├── cross/             # Hypothesis generation (signal + literature + enrichments)
├── scan/              # Automated drug scanning with scoring
├── evidence/          # EvidenceBlock with provenance
├── pubmed/            # NCBI/PubMed (EFetch + ESearch)
├── vocab/             # RxNorm normalization + MeSH + MedDRA grouping
├── dailymed/          # FDA label parsing (SPL XML)
├── trials/            # ClinicalTrials.gov (curl_cffi for Cloudflare)
├── drugbank/          # DrugBank XML (mechanism, interactions, enzymes)
├── opentargets/       # OpenTargets Platform (GraphQL, LRT scores)
├── chembl/            # ChEMBL (mechanism, targets, metabolism)
├── onsides/           # OnSIDES international labels (NLP-extracted)
├── pharmgkb/          # PharmGKB pharmacogenomics (CPIC/DPWG)
├── canada/            # Canada Vigilance (cross-country validation)
├── jader/             # JADER/PMDA Japan (cross-country, JP→EN)
├── anvisa/            # ANVISA Brazil (drug registry, PT↔EN mapping)
├── store/             # BaseDuckDBStore base class (shared singleton + lock)
├── download/          # Shared download utilities (streaming, ZIP, freshness)
├── cache/             # DuckDB HTTP cache (thread-safe singleton)
├── http/              # BaseClient with retry, rate limiting, auth
├── contracts/         # Protocol classes (interfaces)
├── mcp/               # MCP server (47 tools)
└── utils/             # Helpers (validation, time, result)

tests/
├── golden_data/       # JSON fixtures per source
├── test_faers/        # FAERS API tests
├── test_faers_bulk/   # FAERS Bulk tests
├── test_stats/        # Signal detection tests
├── test_cross/        # Hypothesis + investigate tests
├── test_scan/         # Drug scanning tests
├── test_store/        # BaseDuckDBStore tests
├── test_download/     # Download utilities tests
└── test_{source}/     # Per-source tests (pubmed, drugbank, etc.)
```

## Adding a new data source

1. Create `hypokrates/{source}/` with `__init__.py`, `api.py`, `client.py`, `models.py`, `constants.py`, `parser.py`
2. Add the source to the `Source` enum in `constants.py`
3. Configure TTL in `cache/policies.py` and rate limit in `constants.py`
4. Add sync wrapper in `sync.py`
5. Export in `__init__.py`
6. Create golden data in `tests/golden_data/{source}/`
7. Write tests mirroring the `test_faers/` structure

## Commits

Format in Portuguese:

```
type: short description

Types: feat, fix, refactor, docs, style, test, chore, perf, security
```

One concern per commit. Never mix feature + refactoring.

## Security

- Never commit `.env`, API keys or secrets
- Rate limiting is mandatory for every source
- Cache is mandatory — every HTTP call goes through DuckDB

## License

By contributing, you agree that your contribution will be licensed under the [AGPL-3.0](LICENSE).
