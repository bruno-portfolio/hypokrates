# OpenTargets Platform

## What is OpenTargets?

The Open Targets Platform is a comprehensive tool for systematic identification and prioritization of drug targets. Its pharmacovigilance dataset provides FAERS-based log-likelihood ratio (LRT) analysis for drug-adverse event associations.

hypokrates accesses OpenTargets through its [GraphQL API](https://platform-docs.opentargets.org/data-access/graphql-api).

## Coverage

- Drug adverse events with LRT scores from FAERS analysis
- ChEMBL drug ID resolution
- Updated with each OpenTargets release (quarterly)

## Rate Limits

| Condition | Limit |
|-----------|-------|
| No API key needed | 30 requests/minute (conservative estimate) |

OpenTargets does not document official rate limits. hypokrates uses a conservative 30 req/min.

## Functions

- `drug_adverse_events(drug)` — Get all adverse events for a drug with LRT scores
- `drug_safety_score(drug, event)` — Get the LRT score for a specific drug-event pair

The LRT (log-likelihood ratio) score measures how disproportionately an adverse event is reported for a drug compared to all other drugs in FAERS. Higher scores indicate stronger association.

## How it works

1. Drug name is resolved to a ChEMBL ID via OpenTargets search
2. Adverse events are fetched via the `adverseEvents` GraphQL query
3. Each event includes MedDRA code, logLR score, and report count

## Limitations

- Requires drug to be in ChEMBL (most approved drugs are)
- LRT analysis is based on FAERS data and subject to the same biases (voluntary reporting, no denominator)
- OpenTargets performs its own FAERS analysis — results may differ from direct FAERS queries
- A critical value threshold is provided (events below it are not statistically significant)
