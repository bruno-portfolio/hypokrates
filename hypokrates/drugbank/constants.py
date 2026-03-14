"""Constantes do módulo DrugBank."""

from __future__ import annotations

# Namespace XML do DrugBank
DRUGBANK_NAMESPACE = "http://www.drugbank.ca"

# Tag names com namespace
TAG_DRUG = f"{{{DRUGBANK_NAMESPACE}}}drug"
TAG_DRUGBANK_ID = f"{{{DRUGBANK_NAMESPACE}}}drugbank-id"
TAG_NAME = f"{{{DRUGBANK_NAMESPACE}}}name"
TAG_DESCRIPTION = f"{{{DRUGBANK_NAMESPACE}}}description"
TAG_MECHANISM = f"{{{DRUGBANK_NAMESPACE}}}mechanism-of-action"
TAG_PHARMACODYNAMICS = f"{{{DRUGBANK_NAMESPACE}}}pharmacodynamics"
TAG_CATEGORIES = f"{{{DRUGBANK_NAMESPACE}}}categories"
TAG_CATEGORY = f"{{{DRUGBANK_NAMESPACE}}}category"
TAG_SYNONYMS = f"{{{DRUGBANK_NAMESPACE}}}synonyms"
TAG_SYNONYM = f"{{{DRUGBANK_NAMESPACE}}}synonym"
TAG_INTERACTIONS = f"{{{DRUGBANK_NAMESPACE}}}drug-interactions"
TAG_INTERACTION = f"{{{DRUGBANK_NAMESPACE}}}drug-interaction"
TAG_TARGETS = f"{{{DRUGBANK_NAMESPACE}}}targets"
TAG_TARGET = f"{{{DRUGBANK_NAMESPACE}}}target"
TAG_ENZYMES = f"{{{DRUGBANK_NAMESPACE}}}enzymes"
TAG_ENZYME = f"{{{DRUGBANK_NAMESPACE}}}enzyme"
TAG_POLYPEPTIDE = f"{{{DRUGBANK_NAMESPACE}}}polypeptide"
TAG_GENE_NAME = f"{{{DRUGBANK_NAMESPACE}}}gene-name"
TAG_ACTIONS = f"{{{DRUGBANK_NAMESPACE}}}actions"
TAG_ACTION = f"{{{DRUGBANK_NAMESPACE}}}action"
TAG_ORGANISM = f"{{{DRUGBANK_NAMESPACE}}}organism"

# Store DuckDB filename
DRUGBANK_DB_FILENAME = "drugbank.duckdb"
