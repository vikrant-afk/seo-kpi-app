"""Write the KPI matrix to Google Sheets and return the spreadsheet URL.

Two modes:
- If OUTPUT_SHEET_ID is set, append a new dated tab to that master workbook.
- Otherwise create a brand-new spreadsheet.
The service account must have Editor access to the master workbook (if used).
"""
from __future__ import annotations

from datetime import datetime

from . import fail, ok


def _svc(creds):
    from googleapiclient.discovery import build
    return build("sheets", "v4", credentials=creds, cache_discovery=False)


def _values(rows, meta, comparison_on):
    header = ["Metric", "Current", "Previous", "Change %", "Source"] if comparison_on \
        else ["Metric", "Current", "Source"]
    out = [
        [f"{meta['url']}  |  {meta['range']}"],
        [f"Generated {meta['generated_at']}"],
        [],
        header,
    ]
    for r in rows:
        if comparison_on:
            chg = "—" if r["change_pct"] is None else f"{r['change_pct']}%"
            out.append([r["metric"], str(r["current"]), str(r["previous"]), chg, r["source"]])
        else:
            out.append([r["metric"], str(r["current"]), r["source"]])
    return out


def write_sheet(creds, rows, meta, comparison_on, master_id="") -> dict:
    try:
        svc = _svc(creds)
        values =
