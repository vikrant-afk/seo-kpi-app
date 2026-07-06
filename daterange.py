"""Date-range presets and comparison-window resolution. No external deps."""
from __future__ import annotations

from datetime import date, timedelta

PRESETS = {
    "custom": "Custom range",
    "1m": "Last 1 month",
    "3m": "Last 3 months",
    "6m": "Last 6 months",
    "12m": "Last 12 months",
}

COMPARISONS = {
    "none": "No comparison",
    "previous_period": "Compare to previous period",
    "previous_year": "Compare to previous year",
}


def _sub_months(d: date, n: int) -> date:
    """Subtract n calendar months, clamping the day to the target month length."""
    month_index = (d.year * 12 + (d.month - 1)) - n
    year, month = divmod(month_index, 12)
    month += 1
    # clamp day
    if month == 12:
        next_month_first = date(year + 1, 1, 1)
    else:
        next_month_first = date(year, month + 1, 1)
    last_day = (next_month_first - timedelta(days=1)).day
    return date(year, month, min(d.day, last_day))


def resolve_range(preset: str, custom_start: date | None, custom_end: date | None):
    """Return (start, end) as date objects. End defaults to yesterday (GSC data lag)."""
    if preset == "custom":
        if not custom_start or not custom_end:
            raise ValueError("Custom range needs both a start and end date.")
        if custom_start > custom_end:
            raise ValueError("Start date must be on or before end date.")
        return custom_start, custom_end

    end = date.today() - timedelta(days=1)
    months = {"1m": 1, "3m": 3, "6m": 6, "12m": 12}[preset]
    start = _sub_months(end, months) + timedelta(days=1)
    return start, end


def previous_range(start: date, end: date, mode: str):
    """Return (prev_start, prev_end) or None."""
    if mode == "none":
        return None
    if mode == "previous_period":
        length = (end - start).days
        p_end = start - timedelta(days=1)
        p_start = p_end - timedelta(days=length)
        return p_start, p_end
    if mode == "previous_year":
        return _shift_year(start, -1), _shift_year(end, -1)
    return None


def _shift_year(d: date, delta: int) -> date:
    try:
        return d.replace(year=d.year + delta)
    except ValueError:  # Feb 29 -> Feb 28
        return d.replace(year=d.year + delta, day=28)


def iso(d: date) -> str:
    return d.strftime("%Y-%m-%d")
