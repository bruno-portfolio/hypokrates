# hypokrates

> Normalize and cross-reference global public health data for medical hypothesis generation.

Open-source Python library that normalizes and cross-references public health datasets (FAERS, DrugBank, PubMed, WHO, GBD) and exposes them via MCP so any person with access to an LLM can generate medical hypotheses.

## Install

```bash
pip install hypokrates
```

## Quick start

```python
import hypokrates as hp

# Adverse events for a drug (OpenFDA/FAERS)
events = hp.faers.adverse_events("propofol")

# With filters
events = hp.faers.adverse_events("propofol", age_min=65, sex="M")

# Compare drugs
comparison = hp.faers.compare(["propofol", "etomidato"], outcome="hypotension")

# Top reported events
top = hp.faers.top_events("dexmedetomidine", limit=10)
```

## Async

```python
import hypokrates

events = await hypokrates.faers.adverse_events("propofol")
```

## Sync wrapper

```python
from hypokrates.sync import faers

events = faers.adverse_events("propofol")
```

## Status

**Alpha** — Sprint 1 (FAERS foundation). Not for clinical use.

## License

MIT
