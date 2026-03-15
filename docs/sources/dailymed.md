# DailyMed — FDA Drug Labels

## What is DailyMed?

DailyMed is a service from the National Library of Medicine (NLM) that provides the most up-to-date drug labeling submitted to the FDA. Drug labels (Structured Product Labeling / SPL) contain official prescribing information including adverse reactions, warnings, and contraindications.

hypokrates accesses DailyMed through its [public REST API](https://dailymed.nlm.nih.gov/dailymed/app-support-web-services.cfm).

## Coverage

- **140,000+** drug labels (prescription, OTC, veterinary)
- Updated as labels are submitted to FDA
- Labels in SPL XML format (HL7 v3)

## Rate Limits

| Condition | Limit |
|-----------|-------|
| No API key needed | 60 requests/minute (conservative estimate) |

DailyMed does not document official rate limits. hypokrates uses a conservative 60 req/min.

## What hypokrates extracts

hypokrates parses the **Adverse Reactions** section of the SPL XML (LOINC code `34084-4`) and extracts individual adverse event terms. This enables automated cross-referencing of FAERS signals against the official drug label.

## Functions

- `label_events(drug)` — Extract all adverse event terms from the drug's FDA label
- `check_label(drug, event)` — Check if a specific event appears in the drug's label

## Label Matching

`match_event_in_label()` uses **case-insensitive substring matching expanded with MedDRA synonyms**. When checking if an event appears in the label, the function expands the event term to all synonyms in its MedDRA group (35 groups, ~120 aliases) via `expand_event_terms()`.

For example, querying `"anaphylactic shock"` will also match `"anaphylaxis"`, `"anaphylactic reaction"`, and `"anaphylactoid reaction"` in the label text.

This expansion applies both to structured terms extracted from the XML and to the raw text fallback search.

## Limitations

- Not all drugs have SPL labels in DailyMed
- Adverse reactions section varies in structure across labels
- MedDRA synonym coverage is limited to 35 static groups (~120 aliases) — terms outside these groups use literal substring matching only
- Generic drugs may have multiple labels from different manufacturers
