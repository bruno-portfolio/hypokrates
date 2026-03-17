"""Constantes do módulo JADER (Japanese Adverse Drug Event Report)."""

from __future__ import annotations

# Store DuckDB filename
JADER_DB_FILENAME = "jader.duckdb"

# CSV file prefixes (PMDA naming: demoYYYYMM-N.csv, drugYYYYMM-N.csv, etc.)
FILE_DEMO = "demo"
FILE_DRUG = "drug"
FILE_REAC = "reac"
FILE_HIST = "hist"

# Encoding dos CSVs JADER (Shift-JIS / cp932)
ENCODING = "cp932"

# Delimiter
DELIMITER = ","

# Drug role values (Japanese)
ROLE_SUSPECT = "被疑薬"
ROLE_CONCOMITANT = "併用薬"
ROLE_INTERACTING = "相互作用"

# Source caveat — disclaimer para TODOS os outputs JADER
JADER_CAVEAT = (
    "JADER source caveat: Drug/event names translated from Japanese (MedDRA/J). "
    "Cross-country comparison with FAERS/Canada requires caution due to "
    "different reporting cultures, populations, and healthcare systems."
)
