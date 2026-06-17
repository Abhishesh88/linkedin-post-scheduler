"""Tests for Google Sheets client — uses mocked gspread."""

import pytest
from unittest.mock import MagicMock, patch

from src.sheets_client import SheetsClient


@pytest.fixture
def mock_sheets():
    """Create a SheetsClient with mocked gspread."""
    with patch("src.sheets_client.gspread") as mock_gs, \
         patch("src.sheets_client.Credentials") as mock_creds:
        mock_creds.from_service_account_info.return_value = MagicMock()
        mock_gc = MagicMock()
        mock_gs.authorize.return_value = mock_gc

        spreadsheet = MagicMock()
        mock_gc.open_by_key.return_value = spreadsheet

        # Settings tab
        settings_ws = MagicMock()
        settings_ws.get_all_values.return_value = [
            ["voice", "audience", "cta_style", "hashtags"],
            ["conversational, expert", "engineering leaders", "soft question", ""],
        ]

        # Theme Bank tab
        themes_ws = MagicMock()
        themes_ws.get_all_values.return_value = [
            ["theme", "category", "active"],
            ["AI engineering", "AI", "TRUE"],
            ["System design", "Technical", "TRUE"],
            ["Burnout", "Wellbeing", "FALSE"],
        ]

        # Posts tab
        posts_ws = MagicMock()
        posts_ws.get_all_values.return_value = [
            ["week_start", "day", "theme", "draft_text", "char_count", "research_summary",
             "status", "suggested_time", "telegram_msg_id", "feedback", "linkedin_post_id", "published_at"],
        ]

        def get_worksheet(name):
            return {"Settings": settings_ws, "Theme Bank": themes_ws, "Posts": posts_ws}[name]

        spreadsheet.worksheet = get_worksheet

        client = SheetsClient.__new__(SheetsClient)
        client._spreadsheet = spreadsheet
        yield client, spreadsheet, settings_ws, themes_ws, posts_ws


def test_get_settings(mock_sheets):
    client, *_ = mock_sheets
    settings = client.get_settings()
    assert settings["voice"] == "conversational, expert"
    assert settings["audience"] == "engineering leaders"
    assert settings["cta_style"] == "soft question"


def test_get_active_themes(mock_sheets):
    client, *_ = mock_sheets
    themes = client.get_active_themes()
    assert len(themes) == 2
    assert themes[0]["theme"] == "AI engineering"
    assert themes[1]["theme"] == "System design"


def test_inactive_themes_excluded(mock_sheets):
    client, *_ = mock_sheets
    themes = client.get_active_themes()
    theme_names = [t["theme"] for t in themes]
    assert "Burnout" not in theme_names


def test_get_prior_posts_empty(mock_sheets):
    client, *_ = mock_sheets
    posts = client.get_prior_posts(limit=5)
    assert posts == []
