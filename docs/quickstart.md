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

## Configuration

```python
from hypokrates.config import configure

configure(
    openfda_api_key="your-key-here",  # optional, raises rate limits
    ncbi_api_key="your-key-here",     # optional, raises rate limits
    ncbi_email="you@example.com",     # recommended for NCBI
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

Compute disproportionality measures (PRR, ROR, IC) for a drug–event pair:

=== "Async"

    ```python
    from hypokrates.stats import api as stats

    result = await stats.signal("propofol", "bradycardia")
    print(f"PRR: {result.prr.value:.2f} (CI: {result.prr.ci_lower:.2f}–{result.prr.ci_upper:.2f})")
    print(f"ROR: {result.ror.value:.2f}")
    print(f"IC:  {result.ic.value:.2f}")
    print(f"Signal detected: {result.signal_detected}")
    ```

=== "Sync"

    ```python
    from hypokrates.sync import stats

    result = stats.signal("propofol", "bradycardia")
    print(f"PRR: {result.prr.value:.2f} (CI: {result.prr.ci_lower:.2f}–{result.prr.ci_upper:.2f})")
    print(f"ROR: {result.ror.value:.2f}")
    print(f"IC:  {result.ic.value:.2f}")
    print(f"Signal detected: {result.signal_detected}")
    ```

## Step 4 — Search Literature

Search PubMed for published evidence on the drug–event pair:

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

Combine FAERS signal detection with PubMed literature to classify the hypothesis:

=== "Async"

    ```python
    from hypokrates.cross import api as cross

    result = await cross.hypothesis("propofol", "bradycardia")
    print(result.classification)  # novel_hypothesis | emerging_signal | known_association | no_signal
    print(result.summary)
    print(f"Confidence: {result.evidence.confidence}")
    ```

=== "Sync"

    ```python
    from hypokrates.sync import cross

    result = cross.hypothesis("propofol", "bradycardia")
    print(result.classification)  # novel_hypothesis | emerging_signal | known_association | no_signal
    print(result.summary)
    print(f"Confidence: {result.evidence.confidence}")
    ```

## Step 6 — Scan Drug

Automatically scan the top adverse events for a drug and classify each:

=== "Async"

    ```python
    from hypokrates.scan import api as scan

    result = await scan.scan_drug("propofol", top_n=10)
    for item in result.items:
        print(f"#{item.rank} {item.event}: {item.classification.value}")
    print(f"Novel: {result.novel_count}, Emerging: {result.emerging_count}")
    ```

=== "Sync"

    ```python
    from hypokrates.sync import scan

    result = scan.scan_drug("propofol", top_n=10)
    for item in result.items:
        print(f"#{item.rank} {item.event}: {item.classification.value}")
    ```

## Step 7 — Normalize Drug Names

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

## Step 8 — Evidence Provenance

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
from hypokrates.faers import api as faers
from hypokrates.stats import api as stats
from hypokrates.pubmed import api as pubmed
from hypokrates.cross import api as cross


async def main():
    # Optional: configure API keys for higher rate limits
    configure(
        openfda_api_key="your-key",
        ncbi_api_key="your-key",
        ncbi_email="you@example.com",
    )

    drug, event = "propofol", "bradycardia"

    # 1. Top adverse events
    top = await faers.top_events(drug, limit=5)
    print("Top events:", [(e.term, e.count) for e in top.events])

    # 2. Signal detection
    sig = await stats.signal(drug, event)
    print(f"Signal: PRR={sig.prr.value:.2f}, detected={sig.signal_detected}")

    # 3. Literature
    lit = await pubmed.count_papers(drug, event)
    print(f"Papers: {lit.total_count}")

    # 4. Cross-reference
    hyp = await cross.hypothesis(drug, event)
    print(f"Classification: {hyp.classification}")
    print(hyp.summary)


asyncio.run(main())
```

## Next Steps

- [API Reference](api/faers.md) — full function signatures and parameters
- [Signal Detection](concepts/signal-detection.md) — understand PRR, ROR, IC formulas
- [Configuration](guides/configuration.md) — API keys, cache, HTTP settings
