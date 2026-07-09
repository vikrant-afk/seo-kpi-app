"""Ahrefs connector — Domain Rating via the FREE public endpoint (no Apify, no API key).

DR source: GET https://api.ahrefs.com/v3/public/domain-rating-free
  - Free, requires NO API key.
  - Use is subject to the Domain Rating License; attribution is REQUIRED:
    "Domain Rating by Ahrefs" (https://ahrefs.com/). We return it so the report can show it.
  - Response shape: {"domain_rating": {"domain_rating": <float>, "license": "<url>"}}

Referring domains: still the PAID /site-explorer/backlinks-stats endpoint, and only
attempted when an Ahrefs token is provided. If no token (or it fails), ref_domains is
left None and the app falls back to DataForSEO — same behaviour as before.
Parsed defensively so minor field-name differences don't break it.
"""
from __future__ import annotations

import requests

from . import fail, ok

BASE = "https://api.ahrefs.com/v3"


def _get(path, params, token=None):
    """GET an Ahrefs v3 endpoint. Sends Bearer auth only when a token is given."""
    headers = {"Accept": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    r = requests.get(f"{BASE}{path}", params=params, timeout=60, headers=headers)
    if r.status_code == 429:
        raise RuntimeError("Ahrefs rate limit (429) — back off and retry")
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


def get_ahrefs(token=None, domain=None, date=None) -> dict:
    """Domain Rating (free) + optional referring domains (paid, token-gated).

    `token` and `date` are kept for backwards compatibility with the orchestrator:
    DR no longer needs them; they are only used for the optional referring-domains call.
    """
    if not domain:
        return fail("domain missing")
    try:
        # --- Domain Rating: FREE public endpoint, no API key ---
        dr_json = _get("/public/domain-rating-free", {"target": domain, "output": "json"})
        dr_block = _deepfind(dr_json, ["domain_rating"])   # -> inner dict or the float itself
        if isinstance(dr_block, dict):                     # {"domain_rating": {"domain_rating": 6.0, "license": ...}}
            dr = dr_block.get("domain_rating")
            lic = dr_block.get("license")
        else:                                              # already the numeric value
            dr = dr_block
            lic = None
        if lic is None:
            lic = _deepfind(dr_json, ["license"])

        # --- Referring domains: PAID, only if a token is available ---
        ref = None
        if token:
            try:
                bs = _get("/site-explorer/backlinks-stats",
                          {"target": domain, "date": date, "mode": "subdomains", "protocol": "both"},
                          token=token)
                ref = _deepfind(bs, ["live_refdomains", "refdomains", "referring_domains"])
            except Exception:  # noqa: BLE001 — fall back to DataForSEO
                ref = None

        return ok(
            dr=dr,
            ref_domains=ref,
            dr_license=lic,
            dr_attribution="Domain Rating by Ahrefs (https://ahrefs.com/)",
        )
    except Exception as e:  # noqa: BLE001
        return fail(f"{type(e).__name__}: {e}")
