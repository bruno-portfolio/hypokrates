# DrugBank

## What is DrugBank?

DrugBank is a comprehensive drug database containing detailed information about drugs including pharmacology, mechanism of action, drug-drug interactions, metabolizing enzymes, and targets.

hypokrates uses the DrugBank XML dataset, which must be downloaded locally (free academic license).

## Coverage

- **16,000+** drug entries
- Drug-drug interactions, mechanisms, targets, enzymes
- Updated with each DrugBank release

## Setup

1. Register for a free academic license at [go.drugbank.com](https://go.drugbank.com/releases/latest)
2. Download `drugbank_all_full_database.xml.zip` (~175 MB)
3. Extract the XML file
4. Configure the path:

```python
from hypokrates.config import configure
configure(drugbank_path="/path/to/drugbank_all_full_database.xml")
```

The first call to any DrugBank function will parse the XML and store the data in a local DuckDB file (`~/.cache/hypokrates/drugbank.duckdb`). This takes 30-60 seconds but only happens once.

## Rate Limits

DrugBank data is local — no rate limiting applies.

## Functions

- `drug_info(drug)` — Get drug mechanism, targets, enzymes, and interactions
- `drug_interactions(drug)` — Get drug-drug interactions
- `drug_mechanism(drug)` — Get mechanism of action via ChEMBL (online, no DrugBank needed)

## Limitations

- Requires manual download of the XML file (cannot be automated due to license terms)
- Initial parse takes 30-60 seconds (cached in DuckDB after first run)
- Drug name matching is exact (case-insensitive) against DrugBank names
- XML dataset may lag behind the DrugBank website
