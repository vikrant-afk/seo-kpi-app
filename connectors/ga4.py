"""GA4 Data API connector. Returns cur/prev for total users, organic sessions,
and LLM traffic (session source matched to the LLM regex)."""
from __future__ import annotations

import re

from . import fail, ok


def _mk_client(creds):
    from google.analytics.data_v1beta import BetaAnalyticsDataClient
    return BetaAnalyticsDataClient(credentials=creds)


def _pid(prop: str) -> str:
    prop = str(prop)
    return prop if prop.startswith("properties/") else f"properties/{prop}"


def _date_ranges(cur, prev):
    from google.analytics.data_v1beta.types import DateRange
    ranges = [DateRange(start_date=cur[0], end_date=cur[1])]
    if prev:
        ranges.append(DateRange(start_date=prev[0], end_date=prev[1]))
    return ranges


def _dim_index(report, name):
    for i, h in enumerate(report.dimension_headers):
        if h.name == name:
            return i
    return None


def _read_single_metric(report, has_prev):
    """For reports with no explicit dimensions. Returns {'cur','prev'}."""
    out = {"cur": 0, "prev": 0 if has_prev else None}
    if not report.rows:
        return out
    dr_idx = _dim_index(report, "dateRange")
    for row in report.rows:
        val = int(float(row.metric_values[0].value))
        if dr_idx is None:
            out["cur"] = val
        else:
            tag = row.dimension_values[dr_idx].value  # date_range_0 / date_range_1
            out["cur" if tag.endswith("_0") else "prev"] = val
    return out


def get_ga4(creds, property_id, cur, prev, llm_regex) -> dict:
    try:
        from google.analytics.data_v1beta.types import (
            Dimension, Filter, FilterExpression, Metric, RunReportRequest)

        client = _mk_client(creds)
        prop = _pid(property_id)
        ranges = _date_ranges(cur, prev)
        has_prev = prev is not None

        total = client.run_report(RunReportRequest(
            property=prop, date_ranges=ranges, metrics=[Metric(name="totalUsers")]))

        organic = client.run_report(RunReportRequest(
            property=prop, date_ranges=ranges, metrics=[Metric(name="sessions")],
            dimension_filter=FilterExpression(filter=Filter(
                field_name="sessionDefaultChannelGroup",
                string_filter=Filter.StringFilter(value="Organic Search")))))

        src = client.run_report(RunReportRequest(
            property=prop, date_ranges=ranges,
            dimensions=[Dimension(name="sessionSource")],
            metrics=[Metric(name="sessions")], limit=250))

        pat = re.compile(llm_regex, re.IGNORECASE)
        src_dim = _dim_index(src, "sessionSource")
        dr_idx = _dim_index(src, "dateRange")
        llm = {"cur": 0, "prev": 0 if has_prev else None}
        for row in src.rows:
            source = row.dimension_values[src_dim].value or ""
            if not pat.search(source):
                continue
            sessions = int(float(row.metric_values[0].value))
            if dr_idx is None:
                llm["cur"] += sessions
            else:
                tag = row.dimension_values[dr_idx].value
                key = "cur" if tag.endswith("_0") else "prev"
                llm[key] += sessions

        return ok(
            total_users=_read_single_metric(total, has_prev),
            organic_sessions=_read_single_metric(organic, has_prev),
            llm_sessions=llm,
        )
    except Exception as e:  # noqa: BLE001
        return fail(f"{type(e).__name__}: {e}")
