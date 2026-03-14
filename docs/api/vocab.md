# Vocab API

Drug name normalization (RxNorm) and medical term mapping (MeSH).

## `normalize_drug()`

Normalizes a drug name to its generic equivalent via RxNorm.

=== "Async"

    ```python
    from hypokrates.vocab import api as vocab

    result = await vocab.normalize_drug("advil")
    print(result.generic_name)  # "ibuprofen"
    print(result.brand_names)   # ["Advil", "Motrin"]
    print(result.rxcui)         # "5640"
    ```

=== "Sync"

    ```python
    from hypokrates.sync import vocab

    result = vocab.normalize_drug("advil")
    print(result.generic_name)  # "ibuprofen"
    ```

### Parameters

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `name` | `str` | required | Drug name (brand or generic) |
| `use_cache` | `bool` | `True` | Use DuckDB cache (90-day TTL) |

## `map_to_mesh()`

Maps a medical term to its MeSH (Medical Subject Headings) equivalent via NCBI E-utilities.

=== "Async"

    ```python
    result = await vocab.map_to_mesh("aspirin")
    print(result.mesh_term)     # "Aspirin"
    print(result.mesh_id)       # "D001241"
    print(result.tree_numbers)  # ["D02.455.426.559.389.657.109", ...]
    ```

=== "Sync"

    ```python
    result = vocab.map_to_mesh("aspirin")
    print(result.mesh_term)     # "Aspirin"
    ```

### Parameters

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `term` | `str` | required | Medical term to map |
| `use_cache` | `bool` | `True` | Use DuckDB cache (90-day TTL) |

## Models

### `DrugNormResult`

| Field | Type | Description |
|-------|------|-------------|
| `original` | `str` | Original input name |
| `generic_name` | `str \| None` | Generic (INN) name |
| `brand_names` | `list[str]` | Known brand names |
| `rxcui` | `str \| None` | RxNorm Concept Unique Identifier |
| `meta` | `MetaInfo` | Provenance metadata |

### `MeSHResult`

| Field | Type | Description |
|-------|------|-------------|
| `query` | `str` | Original query term |
| `mesh_id` | `str \| None` | MeSH Descriptor UI (e.g., "D001241") |
| `mesh_term` | `str \| None` | Preferred MeSH heading |
| `tree_numbers` | `list[str]` | MeSH tree hierarchy codes |
| `meta` | `MetaInfo` | Provenance metadata |

## Rate Limits

| Source | Rate | Cache TTL |
|--------|------|-----------|
| RxNorm | 120 req/min | 90 days |
| MeSH (NCBI) | Shared with PubMed (180/min, 600/min with key) | 90 days |
