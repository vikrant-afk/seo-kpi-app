"""Discover every client the service account can see: all GA4 properties (Admin API)
and all Search Console sites, then best-match them by domain so the app can show a
single client dropdown covering every client added in GA & GSC."""
from __future__ import annotations

import re
from urllib.parse import urlparse


def list_gsc_sites(creds) -> list[str]:
    from googleapiclient.discovery import build
    svc = build("searchconsole", "v1", credentials=creds, cache_discovery=False)
    entries = svc.sites().list().execute().get("siteEntry", [])
    sites = [e["siteUrl"] for e in entries
             if e.get("permissionLevel") not in ("siteUnverifiedUser",)]
    return sorted(sites)


def list_ga4_properties(creds) -> list[dict]:
    from google.analytics.admin import AnalyticsAdminServiceClient
    client = AnalyticsAdminServiceClient(credentials=creds)
    out = []
    for summary in client.list_account_summaries():
        for ps in summary.property_summaries:
            out.append({
                "id": ps.property.split("/")[-1],
                "name": ps.display_name,
                "account": summary.display_name,
            })
    return sorted(out, key=lambda p: p["name"].lower())


def _core(text: str) -> str:
    """Reduce a domain or name to comparable alphanumerics (drop www, TLD, symbols)."""
    text = text.lower()
    if "//" in text or "." in text:
        netloc = urlparse(text if "//" in text else f"https://{text}").netloc or text
        text = netloc.replace("www.", "").split(".")[0]
    return re.sub(r"[^a-z0-9]", "", text)


def site_domain(site: str) -> str:
    if site.startswith("sc-domain:"):
        return site.split("sc-domain:")[1]
    return urlparse(site).netloc.replace("www.", "")


def best_ga4_for(site: str, ga4_props: list[dict]) -> str | None:
    """Return the GA4 property id whose name best matches the GSC site's domain."""
    token = _core(site_domain(site))
    if not token:
        return None
    best, best_score = None, 0
    for p in ga4_props:
        name_core = _core(p["name"])
        score = 0
        if token and (token in name_core or name_core in token):
            score = min(len(token), len(name_core))
        prefix = 0
        for a, b in zip(token, name_core):
            if a != b:
                break
            prefix += 1
        score = max(score, prefix)
        if score > best_score:
            best, best_score = p["id"], score
    return best if best_score >= 4 else None
