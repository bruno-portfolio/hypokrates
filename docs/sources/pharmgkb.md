# PharmGKB

[PharmGKB](https://www.pharmgkb.org/) is the leading open pharmacogenomics knowledge base, providing gene-drug associations, clinical annotations, and dosing guidelines from CPIC, DPWG, and other consortium sources.

## Setup

No setup required — PharmGKB has a free public REST API with no authentication.

## API

### `pgx_drug_info(drug, *, use_cache=True)`

Complete pharmacogenomic profile: annotations + guidelines.

```python
from hypokrates.sync import pharmgkb

result = pharmgkb.pgx_drug_info("warfarin")
print(f"PharmGKB ID: {result.pharmgkb_id}")

for ann in result.annotations:
    print(f"{ann.gene_symbol}: Level {ann.level_of_evidence}")

for gl in result.guidelines:
    print(f"{gl.source}: {gl.name}")
```

### `pgx_annotations(drug, *, min_level="3", use_cache=True)`

Clinical annotations with evidence level filtering.

```python
anns = pharmgkb.pgx_annotations("warfarin", min_level="2A")
for ann in anns:
    cats = ", ".join(ann.annotation_types)
    print(f"{ann.gene_symbol} (Level {ann.level_of_evidence}): {cats}")
```

Evidence levels (strongest → weakest):
- **1A** — Guideline-annotated, variant-drug combination implemented clinically
- **1B** — Guideline-annotated, variant-drug combination
- **2A** — Known functional significance, moderate evidence
- **2B** — Moderate evidence
- **3** — Low evidence
- **4** — Case reports, preliminary evidence

### `pgx_guidelines(drug, *, use_cache=True)`

Dosing guidelines from CPIC, DPWG, CPNDS, RNPGx.

```python
guides = pharmgkb.pgx_guidelines("warfarin")
for gl in guides:
    print(f"{gl.source}: {', '.join(gl.genes)}")
```

## Models

### `PharmGKBAnnotation`

| Field | Type | Description |
|-------|------|-------------|
| `accession_id` | `str` | PharmGKB annotation ID |
| `gene_symbol` | `str` | Gene symbol (e.g., VKORC1, CYP2C9) |
| `level_of_evidence` | `str` | 1A, 1B, 2A, 2B, 3, 4 |
| `annotation_types` | `list[str]` | Toxicity, Dosage, Efficacy, Metabolism/PK |
| `score` | `float` | PharmGKB annotation score |

### `PharmGKBGuideline`

| Field | Type | Description |
|-------|------|-------------|
| `guideline_id` | `str` | PharmGKB guideline ID |
| `name` | `str` | Guideline name |
| `source` | `str` | CPIC, DPWG, CPNDS, RNPGx |
| `genes` | `list[str]` | Associated genes |
| `recommendation` | `bool` | Has dosing recommendation |
| `summary` | `str` | Summary text |

## Integration with hypothesis()

```python
from hypokrates.sync import cross

result = cross.hypothesis(
    "propofol", "bradycardia",
    check_pharmgkb=True,  # adds pharmacogenomics to result
)
for pgx in result.pharmacogenomics:
    print(pgx)  # "CYP2B6 (Level 3) — Metabolism/PK"
```

## Rate Limits

- **Rate:** 60 req/min (conservative, undocumented)
- **Auth:** None required
- **Cache TTL:** 7 days
