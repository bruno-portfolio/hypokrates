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

## Signal detection

Disproportionality analysis (PRR, ROR, IC) for drug-event pairs:

```python
# Async
result = await hp.stats.signal("propofol", "PRIS")
print(result.prr.value)        # PRR point estimate
print(result.signal_detected)  # Heuristic: >=2/3 measures significant

# Sync
from hypokrates.sync import stats
result = stats.signal("propofol", "PRIS")
```

## Evidence blocks

Structured provenance for any result:

```python
from hypokrates.evidence import build_faers_evidence

block = build_faers_evidence(result.meta, result.model_dump())
print(block.limitations)  # [voluntary_reporting, no_denominator, ...]
print(block.disclaimer)
```

## Async

```python
import hypokrates

events = await hypokrates.faers.adverse_events("propofol")
signal = await hypokrates.stats.signal("propofol", "DEATH")
```

## Sync wrapper

```python
from hypokrates.sync import faers, stats

events = faers.adverse_events("propofol")
signal = stats.signal("propofol", "DEATH")
```

## Status

**Alpha** — Sprint 2 (FAERS + signal detection). Not for clinical use.

## License

MIT
