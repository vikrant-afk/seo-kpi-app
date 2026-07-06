"""Google Search Console connector. Overall + non-branded clicks/impressions/CTR,
with optional previous-period comparison."""
from __future__ import annotations

from . import fail, ok


def _service(creds):
    from googleapiclient.discovery import build
    return build("searchconsole", "v1", credentials=creds, cache_discovery=False)


def _totals(service, site, start, end, nb_regex=None):
    body = {"startDate": start, "endDate": end, "dimensions": []}
    if nb_regex:
        body["dimensionFilterGroups"] = [{"filters": [{
            "dimension": "query", "operator": "excludingRegex", "expression": nb_regex}]}]
    rows = service.searchanalytics().query(siteUrl=site, body=body).execute().get("rows", [])
    if not rows:
        return {"clicks": 0, "impressions": 0, "ctr": 0.0}
    r = rows[0]
    return {
        "clicks": int(r.get("clicks", 0)),
        "impressions": int(r.get("impressions", 0)),
        "ctr": round(r.get("ctr", 0.0) * 100, 2),
    }


def _cp(cur_val, prev_val, has_prev):
    return {"cur": cur_val, "prev": prev_val if has_prev else None}


def get_search_console(creds, site, cur, prev, nb_regex) -> dict:
    try:
        service = _service(creds)
        has_prev = prev is not None

        c_all = _totals(service, site, cur[0], cur[1])
        c_nb = _totals(service, site, cur[0], cur[1], nb_regex)
        p_all = _totals(service, site, prev[0], prev[1]) if has_prev else {}
        p_nb = _totals(service, site, prev[0], prev[1], nb_regex) if has_prev else {}

        return ok(
            clicks=_cp(c_all["clicks"], p_all.get("clicks"), has_prev),
            impressions=_cp(c_all["impressions"], p_all.get("impressions"), has_prev),
            nb_clicks=_cp(c_nb["clicks"], p_nb.get("clicks"), has_prev),
            nb_impressions=_cp(c_nb["impressions"], p_nb.get("impressions"), has_prev),
            nb_ctr=_cp(c_nb["ctr"], p_nb.get("ctr"), has_prev),
        )
    except Exception as e:  # noqa: BLE001
        return fail(f"{type(e).__name__}: {e}")
