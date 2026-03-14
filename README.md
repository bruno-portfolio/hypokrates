# hypokrates

> Normalize and cross-reference global public health data for medical hypothesis generation.

Open-source Python library that normalizes and cross-references public health datasets (FAERS, PubMed, DrugBank, WHO, GBD) and exposes them via MCP so any person with access to an LLM can generate medical hypotheses.

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

## PubMed literature search

Search NCBI/PubMed for drug-event literature:

```python
# Count papers
result = await hp.pubmed.count_papers("propofol", "hepatotoxicity")
print(result.total_count)  # 23

# Search with article metadata
result = await hp.pubmed.search_papers("propofol", "hepatotoxicity", limit=5)
for article in result.articles:
    print(f"{article.pmid}: {article.title}")

# Sync
from hypokrates.sync import pubmed
result = pubmed.search_papers("propofol", "hepatotoxicity")
```

## Hypothesis generation

Cross-reference FAERS signal + PubMed literature to classify hypotheses:

```python
# Async
result = await hp.cross.hypothesis("propofol", "PRIS")
print(result.classification)    # novel_hypothesis | emerging_signal | known_association | no_signal
print(result.summary)           # Human-readable summary
print(result.literature_count)  # Papers found
print(result.signal.prr.value)  # Underlying signal data

# Sync
from hypokrates.sync import cross
result = cross.hypothesis("propofol", "PRIS")

# Custom thresholds
result = await hp.cross.hypothesis(
    "propofol", "PRIS",
    novel_max=2,       # <= 2 papers = novel (default: 0)
    emerging_max=10,   # <= 10 papers = emerging (default: 5)
    use_mesh=True,     # Use MeSH qualifiers for precision
)
```

## Drug scanning

Automated scan of top adverse events with hypothesis classification:

```python
# Scan top 20 events for propofol (async)
result = await hp.scan.scan_drug("propofol", top_n=20)

for item in result.items:
    print(f"#{item.rank} {item.event}: {item.classification.value} (score={item.score:.1f})")

print(f"Novel: {result.novel_count}, Emerging: {result.emerging_count}")

# Sync
from hypokrates.sync import scan
result = scan.scan_drug("propofol", top_n=10)
```

## Drug normalization

Normalize drug names (brand → generic) and map to MeSH:

```python
# RxNorm: brand → generic
norm = await hp.vocab.normalize_drug("advil")
print(norm.generic_name)  # "ibuprofen"
print(norm.brand_names)   # ["Advil", "Motrin"]

# MeSH mapping
mesh = await hp.vocab.map_to_mesh("aspirin")
print(mesh.mesh_term)     # "Aspirin"
print(mesh.mesh_id)       # "D001241"

# Sync
from hypokrates.sync import vocab
norm = vocab.normalize_drug("advil")
mesh = vocab.map_to_mesh("aspirin")
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
papers = await hypokrates.pubmed.search_papers("propofol", "DEATH")
hyp = await hypokrates.cross.hypothesis("propofol", "DEATH")
scan_result = await hypokrates.scan.scan_drug("propofol")
norm = await hypokrates.vocab.normalize_drug("advil")
```

## Sync wrapper

```python
from hypokrates.sync import faers, stats, pubmed, cross, scan, vocab

events = faers.adverse_events("propofol")
signal = stats.signal("propofol", "DEATH")
papers = pubmed.search_papers("propofol", "DEATH")
hyp = cross.hypothesis("propofol", "DEATH")
scan_result = scan.scan_drug("propofol")
norm = vocab.normalize_drug("advil")
```

## Status

**Alpha** — Sprint 4 (FAERS + signal detection + PubMed + hypothesis + scan + vocab). Not for clinical use.

## License

MIT
