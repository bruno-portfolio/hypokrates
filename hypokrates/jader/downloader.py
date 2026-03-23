"""JADER download helper — manual download required (PMDA CAPTCHA).

PMDA protects JADER downloads with CAPTCHA, so fully automated download
is not possible. This module provides a helper for loading from a
user-provided ZIP/directory, and the CLI `download jader` command
prints instructions for manual download.
"""

from __future__ import annotations

import logging

logger = logging.getLogger(__name__)

# PMDA download page (requires CAPTCHA)
JADER_DOWNLOAD_PAGE = (
    "https://www.pmda.go.jp/safety/info-services/drugs/adr-info/suspected-adr/0005.html"
)

JADER_INSTRUCTIONS = (
    "JADER requires manual download (PMDA uses CAPTCHA).\n\n"
    "Steps:\n"
    f"1. Visit {JADER_DOWNLOAD_PAGE}\n"
    "2. Navigate to the CSV download page\n"
    "3. Solve the CAPTCHA and download the bulk CSV archive\n"
    "4. Extract the ZIP to a local directory\n"
    "5. Configure hypokrates:\n"
    "   from hypokrates import configure\n"
    "   configure(jader_bulk_path='/path/to/extracted/csvs/')\n"
)
