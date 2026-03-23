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

When searching for a drug, DailyMed may return multiple SPLs (e.g., injectable, tablet, cream, patch, veterinary). hypokrates fetches up to **100 candidates** and ranks them by heuristic score:

| Factor | Score Impact |
|--------|-------------|
| Prescription/systemic forms (injection, tablet, capsule, etc.) | **+25** |
| OTC/topical forms (cream, patch, gel, ointment, etc.) | **-25** |
| Combination products (" AND ", " WITH ", " / " in title) | **-30** |
| Veterinary labels (Covetrus, Dechra, Zoetis, etc.) | **-100** |
| SPL version (revision count, capped at 5) | **+1 to +5** |

Two-pass selection: first prefers SPLs with a formal Adverse Reactions section (LOINC 34084-4), then falls back to any safety section. This ensures:

- **Single-ingredient** labels are preferred over combination products (e.g., acetaminophen alone over acetaminophen+codeine)
- **Systemic formulations** are preferred over topical (e.g., hydrocortisone injection over hydrocortisone cream)
- **Veterinary labels** are excluded
- **Prescription labels** are preferred over OTC

## Indications Extraction

`label_events()` also extracts the "INDICATIONS AND USAGE" section (LOINC `34067-9`) from the same SPL XML — zero extra HTTP calls. The text is available as `LabelEventsResult.indications_text` and used by `check_drug_indication()` to detect indication confounding (e.g., sugammadex + "recurrence of NMB", dexmedetomidine + "delirium").

## Functions

- `label_events(drug)` — Extract all adverse event terms + indications text from the drug's FDA label
- `check_label(drug, event)` — Check if a specific event appears in the drug's label

## Label Matching

`match_event_in_label()` uses a **4-layer matching strategy**:

1. **Substring match** (case-insensitive) — fast, no false positives
2. **MedDRA synonyms** — expands the event to all synonyms in its MedDRA group (45 groups, ~140 aliases) via `expand_event_terms()`, then retries substring match
3. **Word-level match** — all words of the event must be present in a label term, not necessarily contiguous. Catches "pulmonary fibrosis" in "pulmonary infiltrates or fibrosis"
4. **Fuzzy match** — uses `rapidfuzz.fuzz.token_sort_ratio` (threshold ≥ 85) to catch reordered words ("hyperthermia malignant" → "malignant hyperthermia"), BrE/AmE spellings (apnoea/apnea), and minor variations

For example, querying `"anaphylactic shock"` will also match `"anaphylaxis"`, `"anaphylactic reaction"`, and `"anaphylactoid reaction"` in the label text.

All layers apply to both structured terms extracted from the XML and the raw text fallback search.

## Limitations

- Not all drugs have SPL labels in DailyMed
- Adverse reactions section varies in structure across labels
- `label_events()` event count may be inflated — narrative text (boilerplate, section references, FDA contact info) can be captured as "events" because the parser splits by commas/semicolons without MedDRA validation
- MedDRA synonym coverage is limited to 45 static groups (~140 aliases) — terms outside these groups rely on fuzzy matching
- Generic drugs may have multiple labels from different manufacturers
- Fuzzy matching may produce rare false positives for very short terms
- Combination products with " AND " in the title are penalized but some edge cases (e.g., "LIDOCAINE AND EPINEPHRINE") may be incorrectly deprioritized when the combination is the most clinically relevant formulation
