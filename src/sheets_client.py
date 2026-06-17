"""Google Sheets integration — 3 tabs: Settings, Theme Bank, Posts."""

from __future__ import annotations

import json
import logging
import os

from dotenv import load_dotenv
import gspread
from google.oauth2.service_account import Credentials

load_dotenv()
logger = logging.getLogger(__name__)

SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive.readonly",
]

# Posts tab column indices (1-indexed for gspread)
POST_COL_WEEK_START = 1
POST_COL_DAY = 2
POST_COL_THEME = 3
POST_COL_DRAFT = 4
POST_COL_CHARS = 5
POST_COL_RESEARCH = 6
POST_COL_STATUS = 7
POST_COL_TIME = 8
POST_COL_TELEGRAM_ID = 9
POST_COL_FEEDBACK = 10
POST_COL_LINKEDIN_ID = 11
POST_COL_PUBLISHED_AT = 12


class SheetsClient:
    """Manages the 3-tab LinkedIn Post Scheduler sheet."""

    def __init__(self):
        creds_json = os.getenv("GOOGLE_SHEETS_CREDENTIALS", "")
        creds_file = os.getenv("GOOGLE_SHEETS_CREDENTIALS_FILE", "")
        sheet_id = os.getenv("GOOGLE_SHEET_ID", "")

        if creds_json:
            creds_info = json.loads(creds_json)
            creds = Credentials.from_service_account_info(creds_info, scopes=SCOPES)
        elif creds_file and os.path.exists(creds_file):
            creds = Credentials.from_service_account_file(creds_file, scopes=SCOPES)
        else:
            raise ValueError("No Google Sheets credentials. Set GOOGLE_SHEETS_CREDENTIALS or GOOGLE_SHEETS_CREDENTIALS_FILE")

        gc = gspread.authorize(creds)
        self._spreadsheet = gc.open_by_key(sheet_id)
        logger.info("Connected to Google Sheet: %s", sheet_id)

    def _ws(self, name: str):
        return self._spreadsheet.worksheet(name)

    def get_settings(self) -> dict:
        """Read the Settings tab (single row of config)."""
        ws = self._ws("Settings")
        rows = ws.get_all_values()
        if len(rows) < 2:
            raise ValueError("Settings tab is empty — needs header + 1 data row")
        headers = [h.strip().lower() for h in rows[0]]
        values = rows[1]
        return {headers[i]: values[i].strip() if i < len(values) else "" for i in range(len(headers))}

    def get_active_themes(self) -> list[dict]:
        """Read active themes from Theme Bank tab."""
        ws = self._ws("Theme Bank")
        rows = ws.get_all_values()
        if len(rows) < 2:
            return []
        headers = [h.strip().lower() for h in rows[0]]
        themes = []
        for row in rows[1:]:
            entry = {headers[i]: row[i].strip() if i < len(row) else "" for i in range(len(headers))}
            if entry.get("active", "TRUE").upper() == "TRUE":
                themes.append(entry)
        return themes

    def get_prior_posts(self, limit: int = 5) -> list[dict]:
        """Get last N published posts for deduplication."""
        ws = self._ws("Posts")
        rows = ws.get_all_values()
        if len(rows) < 2:
            return []
        headers = [h.strip().lower() for h in rows[0]]
        published = []
        for row in rows[1:]:
            entry = {headers[i]: row[i].strip() if i < len(row) else "" for i in range(len(headers))}
            if entry.get("status", "").lower() == "published":
                published.append(entry)
        return published[-limit:]

    def get_posts_by_status(self, status: str) -> list[dict]:
        """Get posts with a given status, including their row numbers."""
        ws = self._ws("Posts")
        rows = ws.get_all_values()
        if len(rows) < 2:
            return []
        headers = [h.strip().lower() for h in rows[0]]
        results = []
        for i, row in enumerate(rows[1:], start=2):
            entry = {headers[j]: row[j].strip() if j < len(row) else "" for j in range(len(headers))}
            entry["_row"] = i
            if entry.get("status", "").lower() == status.lower():
                results.append(entry)
        return results

    def append_post(self, post_data: dict):
        """Append a new post row to the Posts tab."""
        ws = self._ws("Posts")
        row = [
            post_data.get("week_start", ""),
            post_data.get("day", ""),
            post_data.get("theme", ""),
            post_data.get("draft_text", ""),
            str(post_data.get("char_count", 0)),
            post_data.get("research_summary", ""),
            post_data.get("status", "pending_approval"),
            post_data.get("suggested_time", "09:00 UTC"),
            str(post_data.get("telegram_msg_id", "")),
            post_data.get("feedback", ""),
            post_data.get("linkedin_post_id", ""),
            post_data.get("published_at", ""),
        ]
        ws.append_row(row, value_input_option="USER_ENTERED")
        logger.info("Appended post for %s: %s", post_data.get("day"), post_data.get("theme"))

    def update_post_status(self, row_number: int, status: str, **extra):
        """Update a post's status and optional extra fields."""
        ws = self._ws("Posts")
        ws.update_cell(row_number, POST_COL_STATUS, status)
        if "telegram_msg_id" in extra:
            ws.update_cell(row_number, POST_COL_TELEGRAM_ID, str(extra["telegram_msg_id"]))
        if "feedback" in extra:
            ws.update_cell(row_number, POST_COL_FEEDBACK, extra["feedback"])
        if "linkedin_post_id" in extra:
            ws.update_cell(row_number, POST_COL_LINKEDIN_ID, extra["linkedin_post_id"])
        if "published_at" in extra:
            ws.update_cell(row_number, POST_COL_PUBLISHED_AT, extra["published_at"])
        logger.info("Row %d status → %s", row_number, status)

    def find_post_row_by_telegram_id(self, telegram_msg_id: int) -> dict | None:
        """Find a post row by its Telegram message ID."""
        ws = self._ws("Posts")
        rows = ws.get_all_values()
        if len(rows) < 2:
            return None
        headers = [h.strip().lower() for h in rows[0]]
        for i, row in enumerate(rows[1:], start=2):
            entry = {headers[j]: row[j].strip() if j < len(row) else "" for j in range(len(headers))}
            entry["_row"] = i
            if entry.get("telegram_msg_id", "") == str(telegram_msg_id):
                return entry
        return None
