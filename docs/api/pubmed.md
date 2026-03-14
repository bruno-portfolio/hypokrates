# PubMed API

Search NCBI/PubMed for published literature on drug–adverse event pairs.

```python
from hypokrates.pubmed import api as pubmed  # async
from hypokrates.sync import pubmed            # sync
```

---

## `count_papers()`

Count the number of PubMed papers matching a drug–event query. Makes a single request (ESearch with `rettype=count`).

```python
result = await pubmed.count_papers("propofol", "bradycardia")
print(f"Papers found: {result.total_count}")
print(f"Query used: {result.query_translation}")
```

**Parameters**

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `drug` | `str` | *required* | Drug name |
| `event` | `str` | *required* | Adverse event term |
| `use_mesh` | `bool` | `False` | Use MeSH qualifiers instead of free text |
| `use_cache` | `bool` | `True` | Use DuckDB cache |

**Returns:** [`PubMedSearchResult`](#pubmedsearchresult) (with `total_count`, no articles)

---

## `search_papers()`

Search PubMed and return article metadata. Makes two requests: ESearch (get PMIDs) + ESummary (get metadata).

```python
result = await pubmed.search_papers("propofol", "bradycardia", limit=5)
print(f"Total: {result.total_count}")
for article in result.articles:
    print(f"  [{article.pmid}] {article.title}")
    print(f"    {article.journal} ({article.pub_date})")
```

**Parameters**

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `drug` | `str` | *required* | Drug name |
| `event` | `str` | *required* | Adverse event term |
| `limit` | `int` | `10` | Maximum articles returned |
| `use_mesh` | `bool` | `False` | Use MeSH qualifiers |
| `use_cache` | `bool` | `True` | Use DuckDB cache |

**Returns:** [`PubMedSearchResult`](#pubmedsearchresult) (with articles)

---

## MeSH vs Free Text

!!! tip "When to use MeSH"
    Set `use_mesh=True` when you have valid MeSH terms (e.g., `"Propofol"` as a MeSH heading). MeSH searches are more precise but require exact vocabulary terms. Free text (default) is more forgiving and catches variations.

    ```python
    # Free text (default) — broader, catches synonyms
    result = await pubmed.count_papers("propofol", "bradycardia")

    # MeSH — precise, requires valid MeSH terms
    result = await pubmed.count_papers("propofol", "bradycardia", use_mesh=True)
    ```

## Rate Limits

| Condition | Rate |
|-----------|------|
| No API key | 3 requests/second |
| With NCBI API key | 10 requests/second |

Configure your API key in [Configuration](../guides/configuration.md) to increase limits.

---

## Models

### `PubMedSearchResult`

| Field | Type | Description |
|-------|------|-------------|
| `total_count` | `int` | Total matching papers in PubMed |
| `articles` | `list[PubMedArticle]` | Article metadata (empty for `count_papers`) |
| `query_translation` | `str \| None` | How PubMed interpreted the query |
| `meta` | `MetaInfo` | Provenance metadata |

### `PubMedArticle`

| Field | Type | Description |
|-------|------|-------------|
| `pmid` | `str` | PubMed ID |
| `title` | `str` | Article title |
| `authors` | `list[str]` | Author names |
| `journal` | `str \| None` | Journal name |
| `pub_date` | `str \| None` | Publication date |
| `doi` | `str \| None` | DOI identifier |
