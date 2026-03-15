"""Script para criar segundo golden ZIP (Q4) para testar multi-quarter loading.

2 reports novos, 1 caseid novo + 1 update de caseid existente (100001 v4).
"""

from __future__ import annotations

import csv
import io
import zipfile
from pathlib import Path

DELIMITER = "$"
OUTPUT_DIR = Path(__file__).parent

DEMO_HEADER = [
    "primaryid",
    "caseid",
    "caseversion",
    "i_f_code",
    "event_dt",
    "age",
    "age_cod",
    "sex",
    "reporter_country",
]
DEMO_ROWS = [
    # CASEID 100001 v4 — update do case existente em Q3, dedup deve pegar este
    ["80000010", "100001", "4", "F", "20240101", "45", "YR", "M", "US"],
    # CASEID 100006 — novo case
    ["80000011", "100006", "1", "I", "20241001", "28", "YR", "F", "JP"],
]

DRUG_HEADER = [
    "primaryid",
    "drug_seq",
    "role_cod",
    "drugname",
    "prod_ai",
    "route",
    "dose_amt",
    "dose_unit",
]
DRUG_ROWS = [
    ["80000010", "1", "PS", "PROPOFOL", "PROPOFOL", "Intravenous", "200", "MG"],
    ["80000011", "1", "PS", "SEVOFLURANE", "SEVOFLURANE", "Inhalation", "2", "%"],
]

REAC_HEADER = ["primaryid", "pt", "drug_rec_act"]
REAC_ROWS = [
    ["80000010", "Bradycardia", ""],
    ["80000010", "Malignant hyperthermia", ""],
    ["80000011", "Nausea", ""],
]


def _write_delimited(rows: list[list[str]], header: list[str]) -> str:
    output = io.StringIO()
    writer = csv.writer(output, delimiter=DELIMITER)
    writer.writerow(header)
    for row in rows:
        writer.writerow(row)
    return output.getvalue()


def create_golden_zip_q4() -> Path:
    zip_path = OUTPUT_DIR / "faers_ascii_2024Q4.zip"

    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("ascii/DEMO24Q4.txt", _write_delimited(DEMO_ROWS, DEMO_HEADER))
        zf.writestr("ascii/DRUG24Q4.txt", _write_delimited(DRUG_ROWS, DRUG_HEADER))
        zf.writestr("ascii/REAC24Q4.txt", _write_delimited(REAC_ROWS, REAC_HEADER))

    return zip_path


if __name__ == "__main__":
    path = create_golden_zip_q4()
    print(f"Created: {path}")
