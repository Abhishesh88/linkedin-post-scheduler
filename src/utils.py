"""Shared utilities for LinkedIn Post Scheduler."""

from __future__ import annotations

import logging
import os
from datetime import date, datetime, timedelta


def setup_logging(name: str = "linkedin-scheduler") -> logging.Logger:
    """Configure logging with consistent format."""
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%H:%M:%S",
    )
    return logging.getLogger(name)


def get_week_dates(week_start: date | None = None) -> list[date]:
    """Return Mon-Fri dates for the given week. Defaults to next Monday."""
    if week_start is None:
        today = date.today()
        days_ahead = (7 - today.weekday()) % 7
        if days_ahead == 0 and today.weekday() != 0:
            days_ahead = 7
        week_start = today + timedelta(days=days_ahead)
        if today.weekday() == 0:
            week_start = today

    return [week_start + timedelta(days=i) for i in range(5)]


def current_year() -> int:
    """Return current year from env or system clock."""
    return int(os.getenv("CURRENT_YEAR", datetime.now().year))
