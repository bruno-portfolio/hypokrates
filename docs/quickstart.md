# Quickstart

Install hypokrates and run your first pharmacovigilance query in 5 minutes.

## Installation

```bash
pip install hypokrates
```

For development:

```bash
pip install hypokrates[dev]
```

Optional extras:

```bash
pip install hypokrates[trials]  # ClinicalTrials.gov (Cloudflare bypass)
pip install hypokrates[mcp]     # MCP server for LLM integration
```

## Configuration

```python
from hypokrates.config import configure

configure(
    openfda_api_key="your-key-here",  # optional, raises rate limits
    ncbi_api_key="your-key-here",     # optional, raises rate limits
    ncbi_email="you@example.com",     # recommended for NCBI
    drugbank_path="/path/to/drugbank.xml",  # optional, for DrugBank module
)
```

!!! tip "API keys are optional"
    hypokrates works without API keys, but with lower rate limits.
    See [Configuration](guides/configuration.md) for how to obtain keys.

## Step 1 — Query Adverse Events

Fetch adverse event reports for a drug from the FDA's FAERS database:

=== "Async"

    ```python
    from hypokrates.faers import api as faers

    result = await faers.adverse_events("propofol", limit=10)
    for report in result.reports:
        print(report.safety_report_id, [r.term for r in report.reactions])
    ```

=== "Sync"

    ```python
    from hypokrates.sync import faers

    result = faers.adverse_events("propofol", limit=10)
    for report in result.reports:
        print(report.safety_report_id, [r.term for r in report.reactions])
    ```

## Step 2 — Top Events

Get the most frequently reported adverse events for a drug:

=== "Async"

    ```python
    result = await faers.top_events("propofol", limit=5)
    for event in result.events:
        print(f"{event.term}: {event.count}")
    ```

=== "Sync"

    ```python
    result = faers.top_events("propofol", limit=5)
    for event in result.events:
        print(f"{event.term}: {event.count}")
    ```

## Step 3 — Signal Detection

Compute disproportionality measures (PRR, ROR, IC) for a drug-event pair:

=== "Async"

    ```python
    from hypokrates.stats import api as stats

    result = await stats.signal("propofol", "bradycardia")
    print(f"PRR: {result.prr.value:.2f} (CI: {result.prr.ci_lower:.2f}-{result.prr.ci_upper:.2f})")
    print(f"ROR: {result.ror.value:.2f}")
    print(f"IC:  {result.ic.value:.2f}")
    print(f"Signal detected: {result.signal_detected}")
    ```

=== "Sync"

    ```python
    from hypokrates.sync import stats

    result = stats.signal("propofol", "bradycardia")
    print(f"PRR: {result.prr.value:.2f} (CI: {result.prr.ci_lower:.2f}-{result.prr.ci_upper:.2f})")
    print(f"ROR: {result.ror.value:.2f}")
    print(f"IC:  {result.ic.value:.2f}")
    print(f"Signal detected: {result.signal_detected}")
    ```

## Step 4 — Search Literature

Search PubMed for published evidence on the drug-event pair:

=== "Async"

    ```python
    from hypokrates.pubmed import api as pubmed

    result = await pubmed.search_papers("propofol", "bradycardia", limit=5)
    print(f"Total papers found: {result.total_count}")
    for article in result.articles:
        print(f"  - {article.title} ({article.journal}, {article.pub_date})")
    ```

=== "Sync"

    ```python
    from hypokrates.sync import pubmed

    result = pubmed.search_papers("propofol", "bradycardia", limit=5)
    print(f"Total papers found: {result.total_count}")
    for article in result.articles:
        print(f"  - {article.title} ({article.journal}, {article.pub_date})")
    ```

## Step 5 — Cross-Reference Hypothesis

Combine FAERS signal + PubMed + optional data sources to classify the hypothesis:

=== "Async"

    ```python
    from hypokrates.cross import api as cross

    result = await cross.hypothesis(
        "propofol", "bradycardia",
        check_label=True,        # check FDA label (DailyMed)
        check_trials=True,       # check ClinicalTrials.gov
        check_chembl=True,       # check mechanism (ChEMBL)
        check_opentargets=True,  # check OpenTargets LRT
    )
    print(result.classification)  # novel_hypothesis | emerging_signal | known_association | no_signal
    print(result.summary)
    print(f"Literature: {result.literature_count} papers")
    ```

=== "Sync"

    ```python
    from hypokrates.sync import cross

    result = cross.hypothesis(
        "propofol", "bradycardia",
        check_label=True,
        check_trials=True,
        check_chembl=True,
        check_opentargets=True,
    )
    print(result.classification)
    print(result.summary)
    ```

## Step 6 — Scan Drug

Automatically scan the top adverse events for a drug and classify each:

=== "Async"

    ```python
    from hypokrates.scan import api as scan

    result = await scan.scan_drug(
        "propofol",
        top_n=10,
        check_labels=True,
        check_trials=True,
        check_chembl=True,
        check_opentargets=True,
        check_direction=True,  # compare base vs PS-only PRR (bulk only)
    )
    for item in result.items:
        direction = f" ({item.direction})" if item.direction else ""
        print(f"#{item.rank} {item.event}: {item.classification.value}{direction}")
    print(f"Novel: {result.novel_count}, Emerging: {result.emerging_count}")
    print(f"Data source: {'Bulk (dedup)' if result.bulk_mode else 'API'}")
    ```

=== "Sync"

    ```python
    from hypokrates.sync import scan

    result = scan.scan_drug("propofol", top_n=10, check_labels=True)
    for item in result.items:
        print(f"#{item.rank} {item.event}: {item.classification.value}")
    ```

!!! tip "FAERS Bulk for better accuracy"
    When FAERS quarterly ASCII files are loaded, `scan_drug()` automatically uses
    deduplicated data with role filtering. Use `primary_suspect_only=True` for
    PS-only analysis and `check_direction=True` to compare base vs PS-only PRR.

## Step 7 — FDA Drug Label

Check if an adverse event is listed in the drug's official FDA label:

=== "Async"

    ```python
    from hypokrates.dailymed import api as dailymed

    # All events in the label
    events = await dailymed.label_events("propofol")
    print(events.events[:10])

    # Check specific event
    check = await dailymed.check_label("propofol", "bradycardia")
    print(f"In label: {check.in_label}")
    ```

=== "Sync"

    ```python
    from hypokrates.sync import dailymed

    events = dailymed.label_events("propofol")
    check = dailymed.check_label("propofol", "bradycardia")
    ```

## Step 8 — Clinical Trials

Search for related clinical trials:

=== "Async"

    ```python
    from hypokrates.trials import api as trials

    result = await trials.search_trials("sugammadex", "bradycardia")
    print(f"Total: {result.total_count}, Active: {result.active_count}")
    for t in result.trials:
        print(f"  {t.nct_id}: {t.title} [{t.status}]")
    ```

=== "Sync"

    ```python
    from hypokrates.sync import trials

    result = trials.search_trials("sugammadex", "bradycardia")
    ```

!!! note "Requires curl_cffi"
    ClinicalTrials.gov uses Cloudflare protection. Install `curl_cffi` for this to work:
    `pip install hypokrates[trials]`

## Step 9 — Drug Info (DrugBank & ChEMBL)

Get mechanism, targets, enzymes, and interactions:

=== "ChEMBL (online, no setup)"

    ```python
    from hypokrates.sync import chembl

    mech = chembl.drug_mechanism("sugammadex")
    print(mech.mechanisms)
    ```

=== "DrugBank (offline, needs XML)"

    ```python
    from hypokrates.config import configure
    configure(drugbank_path="/path/to/drugbank.xml")

    from hypokrates.sync import drugbank

    info = drugbank.drug_info("sugammadex")
    print(info.mechanism)
    print(info.interactions[:5])
    ```

## Step 10 — OpenTargets Safety

Get FAERS-based LRT scores from OpenTargets:

=== "Async"

    ```python
    from hypokrates.opentargets import api as ot

    events = await ot.drug_adverse_events("sugammadex")
    for e in events.events[:5]:
        print(f"{e.event}: logLR={e.llr:.1f}")

    score = await ot.drug_safety_score("sugammadex", "bradycardia")
    print(f"logLR: {score.llr}")
    ```

=== "Sync"

    ```python
    from hypokrates.sync import opentargets

    events = opentargets.drug_adverse_events("sugammadex")
    score = opentargets.drug_safety_score("sugammadex", "bradycardia")
    ```

## Step 11 — Normalize Drug Names

Resolve brand names to generic names and map to MeSH:

=== "Async"

    ```python
    from hypokrates.vocab import api as vocab

    norm = await vocab.normalize_drug("advil")
    print(f"{norm.original} -> {norm.generic_name}")  # advil -> ibuprofen

    mesh = await vocab.map_to_mesh("aspirin")
    print(f"{mesh.query} -> {mesh.mesh_term} ({mesh.mesh_id})")
    ```

=== "Sync"

    ```python
    from hypokrates.sync import vocab

    norm = vocab.normalize_drug("advil")
    print(f"{norm.original} -> {norm.generic_name}")
    ```

## Step 12 — Evidence Provenance

Every result carries full provenance metadata:

```python
print(result.evidence.source)        # "FAERS+PubMed"
print(result.evidence.retrieved_at)  # datetime of query
print(result.evidence.limitations)   # [voluntary_reporting, no_denominator, no_causation]
print(result.evidence.methodology)   # description of the method
print(result.evidence.disclaimer)    # clinical disclaimer
```

## Complete Script

```python
import asyncio
from hypokrates.config import configure
from hypokrates.cross import api as cross
from hypokrates.scan import api as scan
from hypokrates.opentargets import api as ot


async def main():
    configure(
        openfda_api_key="your-key",
        ncbi_api_key="your-key",
        ncbi_email="you@example.com",
    )

    # Full hypothesis with all sources
    hyp = await cross.hypothesis(
        "sugammadex", "bradycardia",
        check_label=True,
        check_trials=True,
        check_chembl=True,
        check_opentargets=True,
    )
    print(f"{hyp.classification}: {hyp.summary}")

    # Full drug scan
    result = await scan.scan_drug(
        "sugammadex",
        top_n=15,
        check_labels=True,
        check_chembl=True,
        check_opentargets=True,
    )
    for item in result.items:
        print(f"#{item.rank} {item.event}: {item.classification.value} (score={item.score:.1f})")


asyncio.run(main())
```

## Next Steps

- [API Reference](api/faers.md) — full function signatures and parameters
- [Signal Detection](concepts/signal-detection.md) — understand PRR, ROR, IC formulas
- [Configuration](guides/configuration.md) — API keys, cache, HTTP settings
- [Data Sources](sources/index.md) — all supported databases
