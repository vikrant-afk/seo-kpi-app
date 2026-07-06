"""Ahrefs API v3 connector — Domain Rating + Referring Domains (no Apify).

Auth: Bearer token (Ahrefs API v3 key). Base https://api.ahrefs.com/v3.
Parsed defensively so minor field-name differences don't break it; if referring
domains can't be read from Ahrefs, the app falls back to DataForSEO.
"""
from __future__ import annotations

import requests

from . import fail, not_configured, ok

BASE = "https://api.ahrefs.com/v3"


def _get(path, token, params):
    r = requests.get(f"{BASE}{path}", params=params, timeout=60,
                     headers={"Authorization": f"Bearer {token}", "Accept": "application/json"})
    r.raise_for_status()
    return r.json()


def _deepfind(obj, keys):
    """Return the first candidate key found anywhere in a nested dict/list."""
    if isinstance(obj, dict):
        for k in keys:
            if k in obj and obj[k] is not None:
                return obj[k]
        for v in obj.values():
            hit = _deepfind(v, keys)
            if hit is not None:
                return hit
    elif isinstance(obj, list):
        for v in obj:
            hit = _deepfind(v, keys)
            if hit is not None:
                return hit
    return None


def get_ahrefs(token, domain, date) -> dict:
    if not token:
        return not_configured("AHREFS_API_TOKEN missing")
    try:
        dr_json = _get("/site-explorer/domain-rating", token,
                       {"target": domain, "date": date, "protocol": "both"})
        dr = _deepfind(dr_json, ["domain_rating"])
        if isinstance(dr, dict):                      # {"domain_rating": {"domain_rating": 6}}
            dr = _deepfind(dr, ["domain_rating"])

        ref = None
        try:
            bs = _get("/site-explorer/backlinks-stats", token,
                      {"target": domain, "date": date, "mode": "subdomains", "protocol": "both"})
            ref = _deepfind(bs, ["live_refdomains", "refdomains", "referring_domains"])
        except Exception:                             # noqa: BLE001 — fall back to DataForSEO
            ref = None

        return ok(dr=dr, ref_domains=ref)
    except Exception as e:  # noqa: BLE001
        return fail(f"{type(e).__name__}: {e}")
