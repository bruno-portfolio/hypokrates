# Signal Detection API

Compute disproportionality measures (PRR, ROR, IC) for drug–event pairs using FAERS data.

```python
from hypokrates.stats import api as stats  # async
from hypokrates.sync import stats           # sync
```

---

## `signal()`

Calculate a disproportionality signal for a drug–event pair.

Fetches four counts from FAERS (drug+event, drug total, event total, N total), builds a 2x2 contingency table, and computes PRR, ROR, and IC (simplified).

```python
result = await stats.signal("propofol", "bradycardia")

print(f"Reports: {result.table.a}")
print(f"PRR: {result.prr.value:.2f} [{result.prr.ci_lower:.2f}, {result.prr.ci_upper:.2f}]")
print(f"ROR: {result.ror.value:.2f} [{result.ror.ci_lower:.2f}, {result.ror.ci_upper:.2f}]")
print(f"IC:  {result.ic.value:.2f} [{result.ic.ci_lower:.2f}, {result.ic.ci_upper:.2f}]")
print(f"Signal: {result.signal_detected}")
```

**Parameters**

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `drug` | `str` | *required* | Generic drug name (e.g., `"propofol"`) |
| `event` | `str` | *required* | MedDRA preferred term (e.g., `"BRADYCARDIA"`) |
| `use_cache` | `bool` | `True` | Use DuckDB cache |

**Returns:** [`SignalResult`](#signalresult)

!!! warning "`signal_detected` is a heuristic"
    The `signal_detected` field is `True` when **at least 2 of 3** measures are significant **and** there are at least 3 co-reports. This is a screening convenience — each regulatory agency uses different criteria (FDA: EBGM/GPS, EMA: PRR, Uppsala: IC). Always evaluate the individual measures for clinical decisions.

---

## Formulas

### PRR — Proportional Reporting Ratio

\[
PRR = \frac{a / (a + b)}{c / (c + d)}
\]

Confidence interval (Rothman-Greenland):

\[
\ln(PRR) \pm 1.96 \times \sqrt{\frac{1}{a} - \frac{1}{a+b} + \frac{1}{c} - \frac{1}{c+d}}
\]

Signal threshold: **CI lower bound > 1.0**

### ROR — Reporting Odds Ratio

\[
ROR = \frac{a \times d}{b \times c}
\]

Confidence interval (Woolf's method):

\[
\ln(ROR) \pm 1.96 \times \sqrt{\frac{1}{a} + \frac{1}{b} + \frac{1}{c} + \frac{1}{d}}
\]

Signal threshold: **CI lower bound > 1.0**

### IC — Information Component (Simplified)

\[
IC = \log_2 \frac{a \times N}{(a + b)(a + c)}
\]

Variance and confidence interval:

\[
V = \frac{1}{a \times (\ln 2)^2}, \quad IC_{025} = IC - 1.96 \times \sqrt{V}
\]

Signal threshold: **CI lower bound > 0**

!!! note
    This is the simplified IC formula, **not** the full BCPNN (Bayesian Confidence Propagation Neural Network) with Beta priors described in Bate et al. (2002). Full BCPNN is planned for a future release.

---

## Models

### `SignalResult`

Complete signal detection result.

| Field | Type | Description |
|-------|------|-------------|
| `drug` | `str` | Drug name |
| `event` | `str` | Event term |
| `table` | `ContingencyTable` | 2x2 contingency table |
| `prr` | `DisproportionalityResult` | PRR with CI |
| `ror` | `DisproportionalityResult` | ROR with CI |
| `ic` | `DisproportionalityResult` | IC simplified with CI |
| `signal_detected` | `bool` | Heuristic: >= 2 significant measures |
| `meta` | `MetaInfo` | Provenance metadata |

### `ContingencyTable`

2x2 table for disproportionality analysis.

|  | Event E | Not E |
|--|---------|-------|
| **Drug D** | a | b |
| **Not D** | c | d |

| Field | Type | Description |
|-------|------|-------------|
| `a` | `int` | Reports with drug D **and** event E |
| `b` | `int` | Reports with drug D **without** event E |
| `c` | `int` | Reports **without** drug D **with** event E |
| `d` | `int` | Reports **without** drug D **without** event E |
| `n` | `int` | Total: a + b + c + d (property) |

### `DisproportionalityResult`

Result of a single measure (PRR, ROR, or IC).

| Field | Type | Description |
|-------|------|-------------|
| `measure` | `str` | `"PRR"`, `"ROR"`, or `"IC"` |
| `value` | `float` | Point estimate |
| `ci_lower` | `float` | 95% CI lower bound |
| `ci_upper` | `float` | 95% CI upper bound |
| `significant` | `bool` | `ci_lower > 1.0` (PRR/ROR) or `ci_lower > 0` (IC) |
