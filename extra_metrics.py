"""Prompt-driven extra metrics.

The custom prompt can request MORE metrics. To stay safe and predictable, the
prompt can only select from a fixed CATALOG of GA4/GSC fields - it can never run
an arbitrary query. Selection is by keyword match, so it works even with no LLM
key configured. Each selected metric is fetched and returned as an extra report
row tagged "from prompt".
"""
from __future__ import annotations

GA4_METRICS = {
    "new_users":            ("New Users", "GA4", ["new user", "new users"]),
    "engaged_sessions":     ("Engaged Sessions", "GA4", ["engaged session"]),
    "avg_session_duration": ("Avg Session Duration (s)", "GA4",
                             ["session duration", "avg session", "engagement time", "time on site"]),
    "views":                ("Views", "GA4", ["pageview", "page view", "views", "screen view"]),
    "event_count":          ("Event Count", "GA4", ["event count", "events"]),
    "conversions":          ("Conversions", "GA4", ["conversion", "key event"]),
    "bounce_rate_all":      ("Bounce Rate (All)", "GA4", ["bounce"]),
    "total_sessions":       ("Total Sessions", "GA4", ["total session", "all sessions", "sessions overall"]),
}
GA4_API = {
    "new_users": "newUsers", "engaged_sessions": "engagedSessions",
    "avg_session_duration": "averageSessionDuration", "views": "screenPageViews",
    "event_count": "eventCount", "conversions": "conversions",
    "bounce_rate_all": "bounceRate", "total_sessions": "sessions",
}
GSC_METRICS = {
    "avg_position": ("Avg Position (All)", "GSC", ["average position", "avg position", "ranking position", "position"]),
    "overall_ctr":  ("Overall CTR", "GSC", ["overall ctr", "average ctr", "ctr overall", "click through"]),
    "top_query":    ("Top Query", "GSC", ["top query", "best keyword", "top keyword", "top search"]),
    "top_page":     ("Top Page", "GSC", ["top page", "best page", "top landing"]),
}

CATALOG = {**GA4_METRICS, **GSC_METRICS}


def supported_list():
    return ", ".join(v[0] for v in CATALOG.values())


def _row(label, value, source):
    return {"metric": label, "current": value, "previous": "-",
            "change_pct": None, "source": source + " - from prompt"}


def _select(prompt):
    p = (prompt or "").lower()
    return [k for k, (_l, _s, syns) in CATALOG.items() if any(s in p for s in syns)]


def _fmt_ga4(key, raw):
    try:
        val = float(raw)
    except (TypeError, ValueError):
        return "-"
    if key == "bounce_rate_all":
        return str(round(val * 100, 2)) + "%"
    if key == "avg_session_duration":
        return round(val)
    return int(val)


def _fetch_ga4(keys, creds, ga4_id, cur):
    keys = [k for k in keys if k in GA4_API]
    if not keys or not creds or not ga4_id:
        return []
    from google.analytics.data_v1beta import BetaAnalyticsDataClient
    from google.analytics.data_v1beta.types import DateRange, Metric, RunReportRequest
    client = BetaAnalyticsDataClient(credentials=creds)
    prop = ga4_id if str(ga4_id).startswith("properties/") else "properties/" + str(ga4_id)
    rep = client.run_report(RunReportRequest(
        property=prop, date_ranges=[DateRange(start_date=cur[0], end_date=cur[1])],
        metrics=[Metric(name=GA4_API[k]) for k in keys]))
    vals = rep.rows[0].metric_values if rep.rows else []
    out = []
    for i, k in enumerate(keys):
        raw = vals[i].value if i < len(vals) else None
        out.append(_row(GA4_METRICS[k][0], _fmt_ga4(k, raw), "GA4"))
    return out


def _fetch_gsc(keys, creds, site, cur):
    keys = [k for k in keys if k in GSC_METRICS]
    if not keys or not creds or not site:
        return []
    from googleapiclient.discovery import build
    svc = build("searchconsole", "v1", credentials=creds, cache_discovery=False)
    out = []
    if "avg_position" in keys or "overall_ctr" in keys:
        body = {"startDate": cur[0], "endDate": cur[1], "dimensions": []}
        rows = svc.searchanalytics().query(siteUrl=site, body=body).execute().get("rows", [])
        r = rows[0] if rows else {}
        if "avg_position" in keys:
            out.append(_row("Avg Position (All)", round(r.get("position", 0), 1), "GSC"))
        if "overall_ctr" in keys:
            out.append(_row("Overall CTR", str(round(r.get("ctr", 0) * 100, 2)) + "%", "GSC"))
    for key, dim, label in [("top_query", "query", "Top Query"), ("top_page", "page", "Top Page")]:
        if key in keys:
            body = {"startDate": cur[0], "endDate": cur[1], "dimensions": [dim], "rowLimit": 1}
            rows = svc.searchanalytics().query(siteUrl=site, body=body).execute().get("rows", [])
            if rows:
                r = rows[0]
                out.append(_row(label, str(r["keys"][0]) + " (" + str(int(r.get("clicks", 0))) + " clicks)", "GSC"))
            else:
                out.append(_row(label, "-", "GSC"))
    return out


def fetch_from_prompt(prompt, creds, ga4_id, gsc_site, cur):
    """Return extra report rows for metrics named in the prompt. Never raises."""
    sel = _select(prompt)
    if not sel:
        return []
    rows = []
    try:
        rows += _fetch_ga4(sel, creds, ga4_id, cur)
    except Exception as e:
        rows.append(_row("Extra GA4 metrics", "ERR: " + str(e)[:50], "GA4"))
    try:
        rows += _fetch_gsc(sel, creds, gsc_site, cur)
    except Exception as e:
        rows.append(_row("Extra GSC metrics", "ERR: " + str(e)[:50], "GSC"))
    return rows
