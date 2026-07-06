"""PageSpeed Insights connector (desktop + mobile performance score, current only)."""
from __future__ import annotations

import requests

from . import fail, ok, not_configured

ENDPOINT = "https://www.googleapis.com/pagespeedonline/v5/runPagespeed"


def _score(url, strategy, key):
    params = {"url": url, "strategy": strategy, "category": "performance"}
    if key:
        params["key"] = key
    r = requests.get(ENDPOINT, params=params, timeout=90)
    r.raise_for_status()
    raw = (r.json().get("lighthouseResult", {}).get("categories", {})
           .get("performance", {}).get("score"))
    return round(raw * 100) if raw is not None else None


def get_pagespeed(url, key) -> dict:
    if not key:
        return not_configured("PAGESPEED_API_KEY missing")
    try:
        return ok(desktop=_score(url, "desktop", key), mobile=_score(url, "mobile", key))
    except Exception as e:  # noqa: BLE001
        return fail(f"{type(e).__name__}: {e}")
