"""DataForSEO connector — Spam Score, Referring Domains, optional DA proxy (no Apify).

Auth: HTTP Basic (login, password). Base https://api.dataforseo.com/v3.
DA proxy: DataForSEO's backlink 'rank' (0–1000) scaled to ~0–100 and clearly labelled
in the report; enabled only when DA_SOURCE=dataforseo, otherwise DA stays blank (Moz-only).
"""
from __future__ import annotations

import base64

import requests

from . import fail, not_configured, ok

BASE = "https://api.dataforseo.com/v3"


def _post(path, login, password, payload):
    tok = base64.b64encode(f"{login}:{password}".encode()).decode()
    r = requests.post(f"{BASE}{path}", json=payload, timeout=60,
                      headers={"Authorization": f"Basic {tok}", "Content-Type": "application/json"})
    r.raise_for_status()
    return r.json()


def _first_item(js):
    """DataForSEO bulk endpoints put the row at tasks[0].result[0] (or .items[0])."""
    try:
        res = js["tasks"][0]["result"]
        if not res:
            return {}
        r0 = res[0]
        if isinstance(r0, dict) and r0.get("items"):
            return r0["items"][0]
        return r0 if isinstance(r0, dict) else {}
    except Exception:  # noqa: BLE001
        return {}


def get_dataforseo(login, password, domain, da_source="none") -> dict:
    if not login or not password:
        return not_configured("DATAFORSEO_LOGIN / DATAFORSEO_PASSWORD missing")
    try:
        spam = _first_item(_post("/backlinks/bulk_spam_score/live",
                                 login, password, [{"targets": [domain]}])).get("spam_score")
        refd = _first_item(_post("/backlinks/bulk_referring_domains/live",
                                 login, password, [{"targets": [domain]}])).get("referring_domains")
        da = None
        if da_source == "dataforseo":
            rank = _first_item(_post("/backlinks/bulk_ranks/live",
                                     login, password, [{"targets": [domain]}])).get("rank")
            da = round(rank / 10) if isinstance(rank, (int, float)) else None
        return ok(spam=spam, ref_domains=refd, da=da)
    except Exception as e:  # noqa: BLE001
        return fail(f"{type(e).__name__}: {e}")
