# ANVISA

## What is ANVISA?

ANVISA (Agência Nacional de Vigilância Sanitária) is Brazil's health regulatory agency, equivalent to the FDA. It maintains a public registry of all medications approved for sale in Brazil, including brand names, active ingredients, regulatory categories, and manufacturers.

hypokrates uses ANVISA's open data portal to provide drug search, name mapping (Portuguese ↔ English), and regulatory context for Brazilian medications.

## Coverage

- **46,000+** registered medications (brands, generics, similars, references)
- Active ingredients, ATC codes, regulatory categories
- Manufacturer and presentation data
- Updated daily by ANVISA ETL process

## Setup

**No setup required.** ANVISA data is fully open (CC BY-ND 3.0). On the first API call, hypokrates automatically downloads the CSV (~5 MB) and indexes it into a local DuckDB store.

Optionally, you can point to a manually downloaded CSV:

```python
from hypokrates.config import configure
configure(anvisa_csv_path="/path/to/TA_CONSULTA_MEDICAMENTOS.CSV")
```

Data is automatically refreshed after 30 days.

## Rate Limits

ANVISA data is local after initial download — no rate limiting applies.

## Functions

- `buscar_medicamento(nome)` — Search by brand name or active ingredient (accent-insensitive, partial match)
- `buscar_por_substancia(substancia, categoria=None)` — Search by active ingredient, optionally filter by category (Genérico, Similar, Referência)
- `listar_apresentacoes(nome)` — List presentations/dosages for a drug
- `mapear_nome(nome)` — Map Brazilian drug name ↔ international name (e.g., dipirona → metamizole)

## Name Mapping

hypokrates includes a built-in mapping of ~95 common drug names between Portuguese and English, covering:

- All anesthesia drugs (propofol, cetamina/ketamine, dexmedetomidina, etc.)
- Common Brazilian drugs (dipirona/metamizole, paracetamol/acetaminophen)
- Cardiovascular, metabolic, neuropsychiatric, and immunobiologic drugs
- Both base forms and salt forms (e.g., CLORIDRATO DE METFORMINA → METFORMIN HYDROCHLORIDE)

For unmapped names, the system falls back to RxNorm normalization.

## MCP Tools

Three MCP tools are available:

- `anvisa_buscar(nome)` — Search drug registry
- `anvisa_genericos(substancia)` — List generics/similars grouped by category
- `anvisa_mapear_nome(nome)` — Map PT ↔ EN drug names

## Data Source

- **URL:** `https://dados.anvisa.gov.br/dados/CONSULTAS/PRODUTOS/TA_CONSULTA_MEDICAMENTOS.CSV`
- **License:** CC BY-ND 3.0 — commercial use allowed with attribution
- **Attribution:** "Fonte: ANVISA — Agência Nacional de Vigilância Sanitária"

## Limitations

- Drug name matching uses normalized substring search — may return false positives for very short queries
- COMPLEMENTO field (presentations) is often empty in the source data
- No structured dosage parsing yet (Phase 2)
- No drug package images available from ANVISA (image_url field reserved for future use)
- Brazilian brand names only — does not cover international brands not registered in Brazil
