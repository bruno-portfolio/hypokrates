# PubMed — NCBI Biomedical Literature

## What is PubMed?

PubMed is a free search engine maintained by the National Center for Biotechnology Information (NCBI) at the U.S. National Library of Medicine. It provides access to citations and abstracts from biomedical and life sciences journals.

hypokrates uses the [NCBI E-utilities API](https://www.ncbi.nlm.nih.gov/books/NBK25501/) to query PubMed programmatically.

## Coverage

- **36+ million citations** from MEDLINE, life science journals, and online books
- Coverage from the **1950s** to present
- Includes citations from journals worldwide, in multiple languages
- New citations added daily

## E-utilities

hypokrates uses two E-utility endpoints:

| Endpoint | Purpose | Used by |
|----------|---------|---------|
| **ESearch** | Search and return PMIDs or counts | `count_papers()`, `search_papers()` |
| **ESummary** | Fetch article metadata by PMIDs | `search_papers()` |

### Request flow

- `count_papers()` — 1 request (ESearch with `rettype=count`)
- `search_papers()` — 2 requests (ESearch + ESummary)

## Rate Limits

| Condition | Limit |
|-----------|-------|
| No API key | 3 requests/second |
| With API key | 10 requests/second |

!!! tip "Getting an API key"
    Register for a free NCBI API key at [ncbiinsights.ncbi.nlm.nih.gov](https://ncbiinsights.ncbi.nlm.nih.gov/2017/11/02/new-api-keys-for-the-e-utilities/). Configure it along with your email:

    ```python
    from hypokrates.config import configure
    configure(
        ncbi_api_key="your-key-here",
        ncbi_email="you@example.com",  # recommended by NCBI
    )
    ```

## MeSH vs Free Text

PubMed supports two search strategies:

### Free Text (default)

Searches title, abstract, and keyword fields using natural language:

```
propofol AND bradycardia AND adverse
```

Broader results — catches synonyms and spelling variations through PubMed's Automatic Term Mapping.

### MeSH Terms

Uses Medical Subject Headings for precise controlled-vocabulary search:

```
"Propofol"[MeSH] AND "Bradycardia/chemically induced"[MeSH]
```

More precise — requires valid MeSH terms. Best when you know the exact MeSH vocabulary.

Use `use_mesh=True` in API calls to enable MeSH search:

```python
result = await pubmed.count_papers("propofol", "bradycardia", use_mesh=True)
```

## Limitations

- **Abstracts only** — hypokrates retrieves metadata and abstracts, not full text
- **English bias** — while PubMed indexes journals in many languages, search is most effective in English
- **Indexing lag** — newly published articles may take days to weeks to appear in PubMed
- **MeSH indexing lag** — MeSH terms are assigned by indexers and may lag behind publication by weeks or months
