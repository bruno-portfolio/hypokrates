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

hypokrates parses **multiple safety sections** of the SPL XML and extracts individual adverse event terms:

| LOINC Code | Section |
|------------|---------|
| `34084-4` | Adverse Reactions |
| `34066-1` | Boxed Warning |
| `34071-1` | Warnings |
| `43685-7` | Warnings and Precautions |

## SPL Selection

When searching for a drug, DailyMed may return multiple SPLs (e.g., injectable, powder, OTC, patch). hypokrates fetches up to **10 candidates** and selects the first SPL that contains at least one safety section (by LOINC code). This avoids picking irrelevant SPLs (like powders for compounding) that have no adverse reactions data.

If no SPL has safety sections, the first result is used as fallback.

## Functions

- `label_events(drug)` — Extract all adverse event terms from the drug's FDA label
- `check_label(drug, event)` — Check if a specific event appears in the drug's label

## Label Matching

`match_event_in_label()` uses a **3-layer matching strategy**:

1. **Substring match** (case-insensitive) — fast, no false positives
2. **MedDRA synonyms** — expands the event to all synonyms in its MedDRA group (35 groups, ~120 aliases) via `expand_event_terms()`, then retries substring match
3. **Fuzzy match** — uses `rapidfuzz.fuzz.token_sort_ratio` (threshold ≥ 85) to catch reordered words ("hyperthermia malignant" → "malignant hyperthermia"), BrE/AmE spellings (apnoea/apnea), and minor variations

For example, querying `"anaphylactic shock"` will also match `"anaphylaxis"`, `"anaphylactic reaction"`, and `"anaphylactoid reaction"` in the label text.

All layers apply to both structured terms extracted from the XML and the raw text fallback search.

## Limitations

- Not all drugs have SPL labels in DailyMed
- Adverse reactions section varies in structure across labels
- MedDRA synonym coverage is limited to 35 static groups (~120 aliases) — terms outside these groups rely on fuzzy matching
- Generic drugs may have multiple labels from different manufacturers
- Fuzzy matching may produce rare false positives for very short terms
