"""Integration test for the generate pipeline logic."""

import pytest
from datetime import date
from src.utils import get_week_dates


def test_get_week_dates_returns_5_days():
    """Week dates always returns exactly 5 weekdays."""
    days = get_week_dates(date(2026, 4, 20))  # Monday
    assert len(days) == 5
    assert days[0] == date(2026, 4, 20)
    assert days[4] == date(2026, 4, 24)


def test_get_week_dates_all_weekdays():
    """All returned dates are Mon-Fri."""
    days = get_week_dates(date(2026, 4, 20))
    for d in days:
        assert d.weekday() < 5  # 0=Mon, 4=Fri
