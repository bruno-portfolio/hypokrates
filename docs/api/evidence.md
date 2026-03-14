# Evidence API

Build evidence blocks with full provenance metadata.

```python
from hypokrates.evidence.builder import build_evidence, build_faers_evidence
from hypokrates.evidence.models import EvidenceBlock, Limitation
```

---

## `build_evidence()`

Create an `EvidenceBlock` from a `MetaInfo` and data dictionary.

```python
from hypokrates.models import MetaInfo
from hypokrates.evidence.builder import build_evidence
from hypokrates.evidence.models import Limitation

evidence = build_evidence(
    meta,
    data={"signal_detected": True, "prr": 2.5},
    limitations=[Limitation.VOLUNTARY_REPORTING, Limitation.NO_CAUSATION],
    methodology="PRR/ROR/IC disproportionality analysis",
    confidence="moderate",
)
```

**Parameters**

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `meta` | `MetaInfo` | *required* | Provenance metadata |
| `data` | `dict[str, object]` | *required* | Key findings / output data |
| `limitations` | `list[Limitation] \| None` | `None` | Known limitations |
| `methodology` | `str \| None` | `None` | Description of the method used |
| `confidence` | `str \| None` | `None` | Confidence label |

**Returns:** [`EvidenceBlock`](#evidenceblock)

---

## `build_faers_evidence()`

Convenience wrapper with pre-defined FAERS limitations (voluntary reporting, no denominator, duplicate reports, missing data, no causation).

```python
from hypokrates.evidence.builder import build_faers_evidence

evidence = build_faers_evidence(
    meta,
    data={"prr": 2.5, "signal_detected": True},
    methodology="PRR/ROR/IC disproportionality",
)
```

**Parameters**

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `meta` | `MetaInfo` | *required* | Provenance metadata |
| `data` | `dict[str, object]` | *required* | Key findings |
| `methodology` | `str \| None` | `None` | Method description |
| `confidence` | `str \| None` | `None` | Confidence label |

**Returns:** [`EvidenceBlock`](#evidenceblock)

---

## Models

### `EvidenceBlock`

Full provenance block attached to every result.

| Field | Type | Description |
|-------|------|-------------|
| `source` | `str` | Data source (e.g., `"OpenFDA/FAERS"`) |
| `source_version` | `str \| None` | API version, if available |
| `query` | `dict[str, object]` | Query parameters used |
| `retrieved_at` | `datetime` | Timestamp of data retrieval |
| `cached` | `bool` | Whether the result came from cache |
| `data` | `dict[str, object]` | Key findings and computed values |
| `limitations` | `list[Limitation]` | Known limitations of the data |
| `disclaimer` | `str` | Clinical disclaimer text |
| `methodology` | `str \| None` | Description of the method |
| `confidence` | `str \| None` | Confidence label (e.g., `"low"`, `"moderate"`, `"high"`) |

### `Limitation`

`StrEnum` of known data source limitations.

| Value | Description |
|-------|-------------|
| `voluntary_reporting` | FAERS relies on voluntary reports — underreporting is common |
| `no_denominator` | No exposed population denominator — cannot calculate incidence rates |
| `duplicate_reports` | FAERS may contain duplicate reports for the same event |
| `missing_data` | Fields like age, sex, and dose are often incomplete |
| `indication_bias` | Drugs used for serious conditions may appear to have more serious events |
| `notoriety_bias` | Widely publicized adverse events may be over-reported |
| `no_causation` | Disproportionality does not imply causation |
