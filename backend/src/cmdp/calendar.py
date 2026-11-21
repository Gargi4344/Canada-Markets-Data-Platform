"""Canadian business-day calendar used by the completeness and freshness checks.

The Bank of Canada does not publish yields or exchange rates on Ontario public holidays,
on federal government holidays (for example the National Day for Truth and
Reconciliation) or on the August Civic Holiday. When calibrated against Valet data from
2017 to 2026, this rule explains every weekday that has no published 10-year yield or
USD/CAD rate.
"""

from __future__ import annotations

from datetime import date, timedelta

import holidays
import polars as pl


def civic_holiday(year: int) -> date:
    """Return the first Monday of August."""
    d = date(year, 8, 1)
    return d + timedelta(days=(7 - d.weekday()) % 7)


def boc_holidays(start: date, end: date) -> dict[date, str]:
    """Return the Bank of Canada non-publishing holidays between two dates."""
    years = range(start.year, end.year + 1)
    cal = holidays.country_holidays(
        "CA", subdiv="ON", years=years, categories=("public", "government")
    )
    out = {d: name for d, name in cal.items() if start <= d <= end}
    for y in years:
        c = civic_holiday(y)
        if start <= c <= end:
            out.setdefault(c, "Civic Holiday")
    return out


def is_business_day(d: date, hol: dict[date, str]) -> bool:
    """Return True when ``d`` is a weekday and not a Bank of Canada holiday."""
    return d.weekday() < 5 and d not in hol


def build_calendar(start: date, end: date) -> pl.DataFrame:
    """Build one row per calendar day with a business-day flag and the holiday name."""
    hol = boc_holidays(start, end)
    days = [start + timedelta(days=i) for i in range((end - start).days + 1)]
    return pl.DataFrame(
        {
            "cal_date": days,
            "is_weekend": [d.weekday() >= 5 for d in days],
            "holiday_name": pl.Series([hol.get(d) for d in days], dtype=pl.String),
            "is_business_day": [is_business_day(d, hol) for d in days],
        }
    )
