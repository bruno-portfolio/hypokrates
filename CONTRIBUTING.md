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
├── cache/             # DuckDB thread-safe cache
├── http/              # Retry, rate limiter, client factory
├── faers/             # OpenFDA/FAERS (client, parser, models)
├── stats/             # PRR, ROR, IC — signal detection
├── evidence/          # EvidenceBlock with provenance
├── contracts/         # Protocol classes (interfaces)
├── pubmed/            # NCBI/PubMed (client, parser, models)
├── cross/             # Hypothesis cross-referencing (FAERS + PubMed)
└── utils/             # Helpers (validation, time, result)

tests/
├── golden_data/       # JSON fixtures per source
├── test_faers/        # FAERS tests
├── test_stats/        # Stats tests
├── test_evidence/     # Evidence tests
├── test_contracts/    # Contracts tests
├── test_pubmed/       # PubMed tests
├── test_cross/        # Cross-reference tests
└── ...
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

By contributing, you agree that your contribution will be licensed under the [MIT License](LICENSE).
