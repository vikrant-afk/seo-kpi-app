"""Write the KPI matrix to Google Sheets and return the spreadsheet URL."""
from __future__ import annotations

from datetime import datetime

from . import fail, ok


def _svc(creds):
    from googleapiclient.discovery import build
    return build("sheets", "v4", credentials=creds, cache_discovery=False)


def _values(rows, meta, comparison_on):
    if comparison_on:
        header = ["Metric", "Current", "Previous", "Change %", "Source"]
    else:
        header = ["Metric", "Current", "Source"]
    out = [
        [meta["url"] + "  |  " + meta["range"]],
        ["Generated " + meta["generated_at"]],
        [],
        header,
    ]
    for r in rows:
        if comparison_on:
            chg = "-" if r["change_pct"] is None else str(r["change_pct"]) + "%"
            out.append([r["metric"], str(r["current"]), str(r["previous"]), chg, r["source"]])
        else:
            out.append([r["metric"], str(r["current"]), r["source"]])
    return out


def write_sheet(creds, rows, meta, comparison_on, master_id=""):
    try:
        svc = _svc(creds)
        values = _values(rows, meta, comparison_on)
        title_tab = (meta["domain"] + " " + meta["range"])[:95]

        if master_id:
            svc.spreadsheets().batchUpdate(spreadsheetId=master_id, body={
                "requests": [{"addSheet": {"properties": {"title": _uniq(svc, master_id, title_tab)}}}]
            }).execute()
            tab = _last_tab(svc, master_id)
            svc.spreadsheets().values().update(
                spreadsheetId=master_id, range="'" + tab + "'!A1",
                valueInputOption="RAW", body={"values": values}).execute()
            sid = master_id
        else:
            created = svc.spreadsheets().create(body={
                "properties": {"title": meta["domain"] + " KPIs " + meta["range"]},
                "sheets": [{"properties": {"title": "KPIs"}}],
            }).execute()
            sid = created["spreadsheetId"]
            svc.spreadsheets().values().update(
                spreadsheetId=sid, range="KPIs!A1",
                valueInputOption="RAW", body={"values": values}).execute()

        return ok(url="https://docs.google.com/spreadsheets/d/" + sid, spreadsheet_id=sid)
    except Exception as e:
        return fail(type(e).__name__ + ": " + str(e))


def _existing_titles(svc, sid):
    meta = svc.spreadsheets().get(spreadsheetId=sid).execute()
    return [s["properties"]["title"] for s in meta.get("sheets", [])]


def _uniq(svc, sid, title):
    existing = set(_existing_titles(svc, sid))
    if title not in existing:
        return title
    return (title + " " + datetime.now().strftime("%H%M%S"))[:99]


def _last_tab(svc, sid):
    return _existing_titles(svc, sid)[-1]
