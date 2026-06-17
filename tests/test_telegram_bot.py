"""Tests for Telegram bot message formatting and callback parsing."""

import pytest
from src.telegram_bot import format_draft_message, parse_callback_data


def test_format_draft_message():
    """Draft message includes theme, text, and char count."""
    msg = format_draft_message(
        day="2026-04-21",
        weekday="Tuesday",
        theme="AI engineering",
        draft_text="This is a test post about AI.",
        char_count=28,
        suggested_time="09:00 UTC",
    )
    assert "Tuesday" in msg
    assert "AI engineering" in msg
    assert "This is a test post about AI." in msg
    assert "28" in msg


def test_parse_callback_approve():
    """Approve callback data is parsed correctly."""
    result = parse_callback_data("approve_5")
    assert result == {"action": "approve", "row": 5}


def test_parse_callback_reject():
    """Reject callback data is parsed correctly."""
    result = parse_callback_data("reject_12")
    assert result == {"action": "reject", "row": 12}


def test_parse_callback_invalid():
    """Invalid callback data returns None."""
    result = parse_callback_data("invalid_data")
    assert result is None
