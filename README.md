# hypokrates

> Normalize and cross-reference global public health data for medical hypothesis generation.

Open-source Python library that normalizes and cross-references public health datasets (FAERS, PubMed, DailyMed, ClinicalTrials.gov, DrugBank, OpenTargets, ChEMBL) and exposes them via MCP so any person with access to an LLM can generate medical hypotheses.

## Install

```bash
pip install hypokrates

# Optional: ClinicalTrials.gov support (Cloudflare bypass)
pip install hypokrates[trials]

# Optional: MCP server
pip install hypokrates[mcp]
```

## Quick start

```python
from hypokrates.config import configure

# Optional: API keys raise rate limits
configure(
    openfda_api_key="your-key",     # 40 -> 240 req/min
    ncbi_api_key="your-key",        # 180 -> 600 req/min
    ncbi_email="you@example.com",
    drugbank_path="/path/to/drugbank.xml",  # Optional: offline drug data
)
```

## Adverse events (FAERS)

```python
from hypokrates.sync import faers

# Top reported events
top = faers.top_events("sugammadex", limit=10)
for e in top.events:
    print(f"{e.term}: {e.count}")

# Individual reports with filters
events = faers.adverse_events("propofol", age_min=65, sex="M", serious=True)

# Compare drugs
comparison = faers.compare(["propofol", "etomidate"], outcome="hypotension")
```

## Signal detection

Disproportionality analysis (PRR, ROR, IC) for drug-event pairs:

```python
from hypokrates.sync import stats

result = stats.signal("sugammadex", "bradycardia")
print(f"PRR: {result.prr.value:.2f}")
print(f"Signal: {result.signal_detected}")  # >= 2/3 measures significant
```

## Literature search (PubMed)

```python
from hypokrates.sync import pubmed

result = pubmed.search_papers("sugammadex", "cardiac arrest", limit=5)
print(f"Total: {result.total_count} papers")
for a in result.articles:
    print(f"  [{a.pmid}] {a.title}")
```

## Hypothesis generation

Cross-reference FAERS signal + PubMed + optional sources:

```python
from hypokrates.sync import cross

result = cross.hypothesis(
    "sugammadex", "bradycardia",
    check_label=True,        # DailyMed FDA label
    check_trials=True,       # ClinicalTrials.gov
    check_chembl=True,       # ChEMBL mechanism
    check_opentargets=True,  # OpenTargets LRT
)
print(result.classification)    # novel_hypothesis | emerging_signal | known_association | no_signal
print(result.summary)
print(result.literature_count)
```

## Drug scanning

Automated scan of top adverse events with classification:

```python
from hypokrates.sync import scan

result = scan.scan_drug(
    "sugammadex",
    top_n=15,
    check_labels=True,
    check_trials=True,
    check_chembl=True,
    check_opentargets=True,
    group_events=True,       # MedDRA synonym grouping (default)
    primary_suspect_only=True,  # PS-only role filter (bulk only)
    check_direction=True,    # compare base PRR vs PS-only PRR
)
for item in result.items:
    direction = f" ({item.direction})" if item.direction else ""
    print(f"#{item.rank} {item.event}: {item.classification.value} (score={item.score:.1f}){direction}")
print(f"Novel: {result.novel_count}, Emerging: {result.emerging_count}")
print(f"Data source: {'Bulk (dedup)' if result.bulk_mode else 'API'}")
```

When FAERS Bulk quarterly files are loaded, `scan_drug()` automatically uses deduplicated data with role filtering (PS-only, suspect, or all). Direction analysis compares base PRR vs PS-only PRR per signal: `"strengthens"` means the signal is pharmacological, `"weakens"` means confounding is probable.

## FDA drug labels (DailyMed)

```python
from hypokrates.sync import dailymed

# All adverse events in the label
events = dailymed.label_events("sugammadex")
print(events.events)  # ["bradycardia", "anaphylaxis", ...]

# Check if specific event is in label
check = dailymed.check_label("sugammadex", "bradycardia")
print(check.in_label)  # True/False
```

## Clinical trials

```python
from hypokrates.sync import trials

result = trials.search_trials("sugammadex", "bradycardia")
print(f"Total: {result.total_count}, Active: {result.active_count}")
for t in result.trials:
    print(f"  {t.nct_id}: {t.title} [{t.status}]")
```

> Requires `curl_cffi`: `pip install hypokrates[trials]`

## Drug info (DrugBank)

```python
from hypokrates.sync import drugbank

# Mechanism, targets, enzymes, interactions
info = drugbank.drug_info("sugammadex")
print(info.mechanism)
print(info.interactions[:5])

# Drug-drug interactions
interactions = drugbank.drug_interactions("sugammadex")
```

> Requires DrugBank XML (free academic license).

## Mechanism of action (ChEMBL)

```python
from hypokrates.sync import chembl

mech = chembl.drug_mechanism("sugammadex")
print(mech.mechanisms)  # action type, targets, gene names
```

## Adverse events (OpenTargets)

```python
from hypokrates.sync import opentargets

# All adverse events with LRT scores
events = opentargets.drug_adverse_events("sugammadex")
for e in events.events[:10]:
    print(f"{e.event}: logLR={e.llr:.1f}, count={e.count}")

# Specific drug-event LRT score
score = opentargets.drug_safety_score("sugammadex", "bradycardia")
print(f"logLR: {score.llr}")
```

## Brazilian drug registry (ANVISA)

```python
from hypokrates.sync import anvisa

# Search by name (partial, accent-insensitive)
result = anvisa.buscar_medicamento("dipirona")
for med in result.medicamentos:
    print(f"{med.nome_produto} ({', '.join(med.substancias)}) — {med.categoria}")

# List generics for an active ingredient
genericos = anvisa.buscar_por_substancia("metformina", categoria="Genérico")

# Map Brazilian ↔ international drug names
mapping = anvisa.mapear_nome("dipirona")
print(f"{mapping.nome_pt} → {mapping.nome_en}")  # DIPIRONA → METAMIZOLE
```

> Auto-downloads ~5 MB CSV on first call. No setup required. Data: CC BY-ND 3.0, Fonte: ANVISA.

## Drug normalization (RxNorm/MeSH)

```python
from hypokrates.sync import vocab

# Brand -> generic
norm = vocab.normalize_drug("advil")
print(f"{norm.original} -> {norm.generic_name}")  # advil -> ibuprofen

# MeSH mapping
mesh = vocab.map_to_mesh("aspirin")
print(f"{mesh.mesh_term} ({mesh.mesh_id})")  # Aspirin (D001241)
```

## Async API

All functions are async-first. The sync wrapper is for convenience:

```python
import asyncio
from hypokrates.cross import api as cross
from hypokrates.scan import api as scan

async def main():
    hyp = await cross.hypothesis("sugammadex", "bradycardia", check_label=True)
    result = await scan.scan_drug("sugammadex", top_n=10)

asyncio.run(main())
```

## MCP Server

hypokrates exposes all functions as MCP tools for LLM integration:

```bash
# Run standalone
python -m hypokrates.mcp

# Or configure in .mcp.json
{
  "mcpServers": {
    "hypokrates": {
      "type": "stdio",
      "command": "python",
      "args": ["-m", "hypokrates.mcp"]
    }
  }
}
```

23 tools available: `adverse_events`, `top_events`, `compare_drugs`, `signal`, `signal_timeline`, `search_papers`, `count_papers`, `hypothesis`, `scan_drug`, `compare_class`, `normalize_drug`, `map_to_mesh`, `label_events`, `check_label`, `search_trials`, `drug_info`, `drug_interactions`, `drug_mechanism`, `drug_metabolism`, `drug_adverse_events`, `drug_safety_score`, `anvisa_buscar`, `anvisa_genericos`, `anvisa_mapear_nome`.

## Data Sources

| Source | Module | Auth | Rate Limit |
|--------|--------|------|------------|
| OpenFDA/FAERS | `faers` | Optional key | 40-240/min |
| FAERS Bulk | `faers_bulk` | Local quarterly ZIPs | Offline (dedup) |
| PubMed | `pubmed` | Optional key | 180-600/min |
| RxNorm | `vocab` | None | 120/min |
| MeSH | `vocab` | Shared w/ PubMed | Shared |
| DailyMed | `dailymed` | None | 60/min |
| ClinicalTrials.gov | `trials` | None (needs curl_cffi) | 50/min |
| DrugBank | `drugbank` | Local XML | Offline |
| OpenTargets | `opentargets` | None | 30/min |
| ChEMBL | `chembl` | None | 30/min |
| ANVISA | `anvisa` | None (auto-download) | Local |

## Status

**Alpha** — 1105+ tests, mypy strict, ruff clean. Not for clinical use.

## License

MIT
