"""Script para criar golden ZIP de teste para FAERS Bulk.

Cria um ZIP com 3 arquivos ASCII ($-delimited): DEMO, DRUG, REAC.
8 reports, 5 caseids únicos (3 com follow-up).

Dados esperados pós-dedup (5 cases):
- CASEID 100001 → primaryid 80000003 (caseversion 3, mais recente)
- CASEID 100002 → primaryid 80000004 (caseversion 2, mais recente)
- CASEID 100003 → primaryid 80000005 (caseversion 1, único)
- CASEID 100004 → primaryid 80000006 (caseversion 1, único)
- CASEID 100005 → primaryid 80000008 (caseversion 2, mais recente)

Contagens esperadas (role_filter=SUSPECT, i.e., PS+SS):
- PROPOFOL + BRADYCARDIA: a=2 (pids 80000003, 80000004)
- PROPOFOL total (drug_total): 3 (pids 80000003, 80000004, 80000005)
- BRADYCARDIA total (event_total): 3 (pids 80000003, 80000004, 80000006)
- N total (deduped): 5

Contagens esperadas (role_filter=PS_ONLY):
- PROPOFOL + BRADYCARDIA: a=1 (pid 80000003 = PS)
- PROPOFOL total (drug_total): 2 (pids 80000003=PS, 80000005=PS)
- BRADYCARDIA total (event_total): 3 (unchanged, reac não tem role)
- N total (deduped): 5

Execute: python tests/golden_data/faers_bulk/create_golden_zip.py
"""

from __future__ import annotations

import csv
import io
import zipfile
from pathlib import Path

DELIMITER = "$"
OUTPUT_DIR = Path(__file__).parent

# --- DEMO data ---
# 8 reports, 5 unique caseids (3 with follow-ups)
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
    # CASEID 100001: 3 versions (1, 2, 3) — dedup keeps primaryid 80000003
    ["80000001", "100001", "1", "I", "20240101", "45", "YR", "M", "US"],
    ["80000002", "100001", "2", "F", "20240101", "45", "YR", "M", "US"],
    ["80000003", "100001", "3", "F", "20240101", "45", "YR", "M", "US"],
    # CASEID 100002: 2 versions (1, 2) — dedup keeps primaryid 80000004
    ["80000004", "100002", "2", "F", "20240215", "62", "YR", "F", "GB"],
    ["80000007", "100002", "1", "I", "20240215", "62", "YR", "F", "GB"],
    # CASEID 100003: 1 version — primaryid 80000005
    ["80000005", "100003", "1", "I", "20240301", "38", "YR", "F", "US"],
    # CASEID 100004: 1 version — primaryid 80000006
    ["80000006", "100004", "1", "I", "20240315", "55", "YR", "M", "DE"],
    # CASEID 100005: 2 versions (1, 2) — dedup keeps primaryid 80000008
    ["80000009", "100005", "1", "I", "20240401", "70", "YR", "M", "US"],
    ["80000008", "100005", "2", "F", "20240401", "70", "YR", "M", "US"],
]

# --- DRUG data ---
# Drugs for each primaryid
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
    # primaryid 80000001 (will be deduped away — caseid 100001 v1)
    ["80000001", "1", "PS", "PROPOFOL 10MG/ML", "PROPOFOL", "Intravenous", "200", "MG"],
    # primaryid 80000002 (will be deduped away — caseid 100001 v2)
    ["80000002", "1", "PS", "PROPOFOL 10MG/ML", "PROPOFOL", "Intravenous", "200", "MG"],
    # primaryid 80000003 (KEPT — caseid 100001 v3) — PS PROPOFOL
    ["80000003", "1", "PS", "PROPOFOL 10MG/ML", "PROPOFOL", "Intravenous", "200", "MG"],
    ["80000003", "2", "C", "MIDAZOLAM", "MIDAZOLAM", "Intravenous", "2", "MG"],
    # primaryid 80000004 (KEPT — caseid 100002 v2) — SS PROPOFOL
    ["80000004", "1", "SS", "DIPRIVAN", "PROPOFOL", "Intravenous", "150", "MG"],
    ["80000004", "2", "PS", "FENTANYL CITRATE", "", "Intravenous", "100", "MCG"],
    # primaryid 80000007 (will be deduped away — caseid 100002 v1)
    ["80000007", "1", "SS", "DIPRIVAN", "PROPOFOL", "Intravenous", "150", "MG"],
    # primaryid 80000005 (KEPT — caseid 100003 v1) — PS PROPOFOL
    ["80000005", "1", "PS", "PROPOFOL", "PROPOFOL", "Intravenous", "200", "MG"],
    # primaryid 80000006 (KEPT — caseid 100004 v1) — PS FENTANYL (no prod_ai, drugname only)
    ["80000006", "1", "PS", "FENTANYL 50MCG", "", "Intravenous", "50", "MCG"],
    ["80000006", "2", "C", "PROPOFOL", "PROPOFOL", "Intravenous", "200", "MG"],
    # primaryid 80000009 (will be deduped away — caseid 100005 v1)
    ["80000009", "1", "PS", "KETAMINE", "KETAMINE", "Intravenous", "100", "MG"],
    # primaryid 80000008 (KEPT — caseid 100005 v2) — PS KETAMINE
    ["80000008", "1", "PS", "KETAMINE", "KETAMINE", "Intravenous", "100", "MG"],
]

# --- REAC data ---
REAC_HEADER = ["primaryid", "pt", "drug_rec_act"]
REAC_ROWS = [
    # primaryid 80000001 (deduped away)
    ["80000001", "Bradycardia", ""],
    # primaryid 80000002 (deduped away)
    ["80000002", "Bradycardia", ""],
    # primaryid 80000003 (KEPT) — BRADYCARDIA + HYPOTENSION
    ["80000003", "Bradycardia", ""],
    ["80000003", "Hypotension", ""],
    # primaryid 80000004 (KEPT) — BRADYCARDIA
    ["80000004", "Bradycardia", ""],
    # primaryid 80000007 (deduped away)
    ["80000007", "Bradycardia", ""],
    # primaryid 80000005 (KEPT) — HYPOTENSION
    ["80000005", "Hypotension", ""],
    # primaryid 80000006 (KEPT) — BRADYCARDIA + DEATH
    ["80000006", "Bradycardia", ""],
    ["80000006", "Death", ""],
    # primaryid 80000009 (deduped away)
    ["80000009", "Hallucination", ""],
    # primaryid 80000008 (KEPT) — HALLUCINATION
    ["80000008", "Hallucination", ""],
]


def _write_delimited(rows: list[list[str]], header: list[str]) -> str:
    """Escreve dados em formato $-delimited."""
    output = io.StringIO()
    writer = csv.writer(output, delimiter=DELIMITER)
    writer.writerow(header)
    for row in rows:
        writer.writerow(row)
    return output.getvalue()


def create_golden_zip() -> Path:
    """Cria ZIP com golden data para testes."""
    zip_path = OUTPUT_DIR / "faers_ascii_2024Q3.zip"

    demo_content = _write_delimited(DEMO_ROWS, DEMO_HEADER)
    drug_content = _write_delimited(DRUG_ROWS, DRUG_HEADER)
    reac_content = _write_delimited(REAC_ROWS, REAC_HEADER)

    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("ascii/DEMO24Q3.txt", demo_content)
        zf.writestr("ascii/DRUG24Q3.txt", drug_content)
        zf.writestr("ascii/REAC24Q3.txt", reac_content)

    return zip_path


if __name__ == "__main__":
    path = create_golden_zip()
    print(f"Created: {path}")
