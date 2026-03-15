# Signal Detection

Signal detection in pharmacovigilance identifies drug–adverse event pairs that occur more frequently than expected. hypokrates uses **disproportionality analysis** — a family of statistical methods that compare observed vs expected reporting frequencies in spontaneous reporting databases like FAERS.

!!! note "Signal ≠ Causation"
    A disproportionality signal means a drug–event pair is reported **more often than expected**. It does not prove the drug *causes* the event. Signals are hypotheses that require further investigation.

## The 2x2 Contingency Table

All disproportionality measures start from a 2x2 table of report counts:

|  | Event E | Not Event E | Total |
|--|:-------:|:-----------:|:-----:|
| **Drug D** | a | b | a + b |
| **Not Drug D** | c | d | c + d |
| **Total** | a + c | b + d | N |

Where:

- **a** = reports mentioning both drug D and event E
- **b** = reports mentioning drug D but not event E
- **c** = reports mentioning event E but not drug D
- **d** = reports mentioning neither drug D nor event E
- **N** = total reports in the database (a + b + c + d)

hypokrates fetches these counts from FAERS using four queries: drug+event, drug total, event total, and N total. The table is constructed from these marginals.

---

## PRR — Proportional Reporting Ratio

The PRR compares the proportion of a specific event among reports for a drug to the proportion of that event among all other drugs.

\[
PRR = \frac{a / (a + b)}{c / (c + d)}
\]

**Interpretation:** A PRR of 3.0 means event E is reported 3 times more frequently with drug D than with all other drugs.

**Confidence interval** (Rothman-Greenland):

\[
\ln(PRR) \pm 1.96 \times \sqrt{\frac{1}{a} - \frac{1}{a+b} + \frac{1}{c} - \frac{1}{c+d}}
\]

**Signal threshold:** CI~95%~ lower bound > 1.0

**Used by:** EMA (European Medicines Agency)

---

## ROR — Reporting Odds Ratio

The ROR compares the odds of event E with drug D to the odds of event E with all other drugs.

\[
ROR = \frac{a \times d}{b \times c}
\]

**Interpretation:** An ROR of 4.0 means the odds of event E being reported with drug D are 4 times higher than with other drugs.

**Confidence interval** (Woolf's method):

\[
\ln(ROR) \pm 1.96 \times \sqrt{\frac{1}{a} + \frac{1}{b} + \frac{1}{c} + \frac{1}{d}}
\]

**Signal threshold:** CI~95%~ lower bound > 1.0

**Advantage over PRR:** Less sensitive to total volume of reports for the drug. Preferred when event rates are not rare.

---

## IC — Information Component (BCPNN)

The IC measures the degree of "surprise" in observing the drug–event combination, using information theory. hypokrates implements the full **BCPNN** (Bayesian Confidence Propagation Neural Network) described in Norén et al. (2006), with Jeffreys prior (α = 0.5).

\[
n^* = N + 4\alpha, \quad IC = \log_2 \frac{(a + \alpha) \times n^*}{(a + b + 2\alpha)(a + c + 2\alpha)}
\]

**Interpretation:** A positive IC means the combination is observed more often than expected. IC = 1 means twice as often; IC = 2 means four times as often. The Bayesian prior shrinks estimates with few reports toward zero, preventing spurious signals from small counts.

**Variance (via trigamma) and confidence interval:**

\[
V = \frac{1}{(\ln 2)^2} \left[ \psi_1(a+\alpha) + \psi_1(a+b+2\alpha) + \psi_1(a+c+2\alpha) - 3\psi_1(n^*) \right]
\]
\[
IC_{025} = IC - 1.96 \times \sqrt{V}
\]

**Signal threshold:** IC~025~ (CI lower bound) > 0

**Used by:** Uppsala Monitoring Centre (WHO)

!!! note "BCPNN shrinkage"
    With few reports (e.g., a < 10), the Jeffreys prior shrinks the IC toward zero and widens the confidence interval, reducing false positives. For large counts, BCPNN converges to the simplified IC formula.

---

## How Regulatory Agencies Use These Measures

| Agency | Primary Method | Threshold |
|--------|---------------|-----------|
| **FDA** | EBGM (Empirical Bayes Geometric Mean) | EB05 > 2.0 |
| **EMA** | PRR | PRR > 2, chi² > 4, N ≥ 3 |
| **Uppsala/WHO** | IC (BCPNN) | IC~025~ > 0 |

hypokrates computes PRR, ROR, and IC (BCPNN). The `signal_detected` heuristic requires **at least 2 of 3** measures to be significant **and** at least 3 co-reports — this is a screening convenience, not a regulatory standard.

---

## Worked Example

Consider **propofol + bradycardia** with the following FAERS counts:

| | Bradycardia | Not Bradycardia | Total |
|-|:-----------:|:---------------:|:-----:|
| **Propofol** | a = 150 | b = 9,850 | 10,000 |
| **Not Propofol** | c = 50,000 | d = 19,940,000 | 19,990,000 |
| **Total** | 50,150 | 19,949,850 | 20,000,000 |

**PRR:**

\[
PRR = \frac{150/10{,}000}{50{,}000/19{,}990{,}000} = \frac{0.015}{0.0025} = 6.0
\]

**ROR:**

\[
ROR = \frac{150 \times 19{,}940{,}000}{9{,}850 \times 50{,}000} = \frac{2{,}991{,}000{,}000}{492{,}500{,}000} \approx 6.07
\]

**IC:**

\[
IC = \log_2 \frac{150 \times 20{,}000{,}000}{10{,}000 \times 50{,}150} = \log_2 \frac{3{,}000{,}000{,}000}{501{,}500{,}000} \approx \log_2 5.98 \approx 2.58
\]

All three measures indicate a strong disproportionality signal for propofol + bradycardia.
