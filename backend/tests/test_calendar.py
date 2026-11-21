"""Tests for the Bank of Canada business-day calendar."""

from datetime import date

from cmdp.calendar import boc_holidays, build_calendar, civic_holiday, is_business_day


def test_civic_holiday_is_first_monday_of_august():
    assert civic_holiday(2024) == date(2024, 8, 5)
    assert civic_holiday(2026) == date(2026, 8, 3)


def test_known_holidays_and_business_days():
    hol = boc_holidays(date(2024, 1, 1), date(2024, 12, 31))
    assert not is_business_day(date(2024, 12, 25), hol)  # Christmas
    assert not is_business_day(date(2024, 2, 19), hol)  # Family Day (Ontario)
    assert not is_business_day(date(2024, 8, 5), hol)  # Civic Holiday
    assert not is_business_day(date(2024, 9, 30), hol)  # Truth and Reconciliation
    assert not is_business_day(date(2024, 3, 9), hol)  # Saturday
    assert is_business_day(date(2024, 4, 1), hol)  # Easter Monday: markets open
    assert is_business_day(date(2024, 3, 12), hol)


def test_build_calendar_shape():
    cal = build_calendar(date(2024, 1, 1), date(2024, 12, 31))
    assert cal.height == 366
    assert cal["is_business_day"].sum() == 366 - 104 - cal["holiday_name"].is_not_null().sum() + (
        cal.filter(cal["is_weekend"] & cal["holiday_name"].is_not_null()).height
    )
