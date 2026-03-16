"""Constantes do módulo Canada Vigilance."""

from __future__ import annotations

# Store DuckDB filename
CANADA_DB_FILENAME = "canada_vigilance.duckdb"

# Bulk download URL
CANADA_BULK_URL = (
    "https://www.canada.ca/content/dam/hc-sc/migration/hc-sc/"
    "dhp-mps/alt_formats/zip/medeff/databasdon/extract_extrait.zip"
)

# $-delimited file names dentro do ZIP
FILE_REPORTS = "Reports.txt"
FILE_REPORT_DRUG = "Report_Drug.txt"
FILE_REACTIONS = "Reactions.txt"
FILE_DRUG_PRODUCT = "Drug_Product.txt"
FILE_DRUG_INGREDIENTS = "Drug_Product_Ingredients.txt"
FILE_REPORT_LINKS = "Report_Links_LX.txt"

# Delimiter para os arquivos
DELIMITER = "$"
