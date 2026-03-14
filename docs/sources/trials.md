# ClinicalTrials.gov

## What is ClinicalTrials.gov?

ClinicalTrials.gov is a registry and results database of publicly and privately funded clinical studies conducted around the world. Maintained by the National Library of Medicine (NLM), it is the largest clinical trials registry globally.

hypokrates accesses ClinicalTrials.gov through its [v2 API](https://clinicaltrials.gov/data-api/about-api).

## Coverage

- **500,000+** registered studies
- International coverage (studies from 200+ countries)
- Updated daily

## Rate Limits

| Condition | Limit |
|-----------|-------|
| No API key needed | 50 requests/minute (documented) |

## TLS Fingerprinting (Cloudflare)

ClinicalTrials.gov uses Cloudflare bot protection that blocks standard Python HTTP clients. hypokrates automatically uses `curl_cffi` when installed:

```bash
pip install hypokrates[trials]
```

Without `curl_cffi`, requests will fail with HTTP 403. The library logs a warning and falls back to httpx (which will likely fail).

## Functions

- `search_trials(drug, event)` — Search for clinical trials related to a drug-event pair

Returns matching trials with NCT ID, title, status, phase, conditions, and interventions.

## Limitations

- ClinicalTrials.gov is a registry, not a results database — trial registration does not imply results are available
- Search matches drug names in the intervention field and event terms in the condition field, which may miss relevant trials
- Trial status may be outdated if investigators do not update their registrations
