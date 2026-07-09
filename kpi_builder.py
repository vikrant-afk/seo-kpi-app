"""Assemble the final KPI rows from connector outputs. No external deps.
Sources: GA4, GSC (both support cur/prev), PageSpeed, Ahrefs API, DataForSEO.
Date-range metrics carry {"cur","prev"}; point-in-time metrics are plain numbers.
"""
from __future__ import annotations


def _cp(source: dict, key):
    if not source or source.get("status") != "ok":
        return _err_marker(source), None
    node = source.get(key)
    if isinstance(node, dict):
        return node.get("cur"), node.get("prev")
    return node, None


def _point(source: dict, key):
    if not source or source.get("status") != "ok":
        return _err_marker(source)
    val = source.get(key)
    return "ERR" if val is None else val


def _err_marker(source):
    if source and source.get("status") == "not_configured":
        return "— not configured"
    return "ERR"


def _pct_change(cur, prev):
    try:
        cur, prev = float(cur), float(prev)
    except (TypeError, ValueError):
        return None
    if prev == 0:
        return None if cur == 0 else float("inf")
    return round((cur - prev) / prev * 100, 1)


def _fmt(val, pct=False):
    if val is None:
        return "—"
    if isinstance(val, str):
        return val
    if pct:
        return f"{val}%"
    if isinstance(val, float):
        return f"{val:.2f}".rstrip("0").rstrip(".")
    return f"{val:,}" if isinstance(val, int) else str(val)


def build_rows(ga4, gsc, psi, ahrefs, dfs) -> list[dict]:
    rows = []

    def add(metric, cur, prev, source, is_pct=False):
        change = _pct_change(cur, prev) if prev is not None else None
        rows.append({
            "metric": metric,
            "current": _fmt(cur, is_pct),
            "previous": _fmt(prev, is_pct) if prev is not None else "—",
            "change_pct": change,
            "source": source,
        })

    # --- GA4 ---
    c, p = _cp(ga4, "total_users");      add("Total Users (Traffic Acquisition)", c, p, "GA4")
    c, p = _cp(ga4, "organic_sessions"); add("Organic Sessions", c, p, "GA4")
    c, p = _cp(ga4, "llm_sessions");     add("LLM Traffic", c, p, "GA4 (LLM regex)")

    # --- Search Console ---
    c, p = _cp(gsc, "clicks");           add("Overall Clicks", c, p, "GSC")
    c, p = _cp(gsc, "impressions");      add("Overall Impressions", c, p, "GSC")
    c, p = _cp(gsc, "nb_clicks");        add("NB Clicks", c, p, "GSC (NB regex)")
    c, p = _cp(gsc, "nb_impressions");   add("NB Impressions", c, p, "GSC (NB regex)")
    c, p = _cp(gsc, "nb_ctr");           add("Avg CTR – NB", c, p, "GSC (NB regex)", True)

    # --- Authority (Ahrefs API + DataForSEO) ---
    da = dfs.get("da") if (dfs and dfs.get("status") == "ok") else None
    if da is not None:
        add("DA (Domain Authority)", da, None, "DataForSEO · rank proxy")
    else:
        add("DA (Domain Authority)", "N/A · Moz", None, "Moz")

    add("Spam Score", _point(dfs, "spam"), None, "DataForSEO")
    add("DR (Domain Rating)", _point(ahrefs, "dr"), None, "Ahrefs (free)")
    # Ahrefs Domain Rating License requires visible attribution when DR is shown.
    if ahrefs and ahrefs.get("dr_attribution"):
        add("DR Source / License", ahrefs["dr_attribution"], None, "Ahrefs")

    # referring domains: Ahrefs first, DataForSEO fallback
    if ahrefs and ahrefs.get("status") == "ok" and ahrefs.get("ref_domains") is not None:
        add("Referring Domains", ahrefs["ref_domains"], None, "Ahrefs")
    elif dfs and dfs.get("status") == "ok" and dfs.get("ref_domains") is not None:
        add("Referring Domains", dfs["ref_domains"], None, "DataForSEO")
    else:
        add("Referring Domains", _point(ahrefs, "ref_domains"), None, "Ahrefs")

    # --- Page Speed ---
    add("Desktop Page Speed", _point(psi, "desktop"), None, "PageSpeed")
    add("Mobile Page Speed", _point(psi, "mobile"), None, "PageSpeed")

    return rows


def to_flat_dict(rows):
    return {r["metric"]: r["current"] for r in rows}
