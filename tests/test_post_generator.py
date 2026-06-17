"""Tests for LinkedIn post generation and deduplication."""

import pytest
from src.post_generator import assign_themes_to_days, format_post_prompt, check_char_limits
from datetime import date


def test_assign_themes_5_themes():
    """5 themes → 1 per day, no repeats."""
    themes = ["A", "B", "C", "D", "E"]
    days = [date(2026, 4, 20), date(2026, 4, 21), date(2026, 4, 22), date(2026, 4, 23), date(2026, 4, 24)]
    assigned = assign_themes_to_days(themes, days)
    assert len(assigned) == 5
    assert len(set(t for _, t in assigned)) == 5


def test_assign_themes_fewer_than_5():
    """3 themes cycle but never repeat on consecutive days."""
    themes = ["A", "B", "C"]
    days = [date(2026, 4, 20), date(2026, 4, 21), date(2026, 4, 22), date(2026, 4, 23), date(2026, 4, 24)]
    assigned = assign_themes_to_days(themes, days)
    assert len(assigned) == 5
    for i in range(len(assigned) - 1):
        assert assigned[i][1] != assigned[i + 1][1], "Consecutive days must not repeat theme"


def test_assign_themes_more_than_5():
    """15 themes → only 5 selected, no repeats."""
    themes = [f"theme_{i}" for i in range(15)]
    days = [date(2026, 4, 20 + i) for i in range(5)]
    assigned = assign_themes_to_days(themes, days)
    assert len(assigned) == 5
    assert len(set(t for _, t in assigned)) == 5


def test_format_post_prompt():
    """Prompt template is populated correctly."""
    prompt = format_post_prompt(
        theme="AI engineering",
        day="2026-04-21",
        weekday="Tuesday",
        voice="conversational",
        audience="engineering leaders",
        cta_style="soft question",
        hashtags="",
        research_summary="Some research data here",
        prior_posts_this_week="None yet",
        prior_published="None",
    )
    assert "AI engineering" in prompt
    assert "Tuesday" in prompt
    assert "Some research data here" in prompt


def test_check_char_limits():
    """Posts over 3000 chars flagged, over 1500 warned."""
    short = "x" * 100
    medium = "x" * 1600
    long_post = "x" * 3100

    assert check_char_limits(short) == {"ok": True, "warning": False, "chars": 100}
    assert check_char_limits(medium) == {"ok": True, "warning": True, "chars": 1600}
    assert check_char_limits(long_post) == {"ok": False, "warning": True, "chars": 3100}
