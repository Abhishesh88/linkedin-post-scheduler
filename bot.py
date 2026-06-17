#!/usr/bin/env python3
"""Telegram bot that listens for Approve/Reject button clicks in real-time.

On Approve: updates Google Sheets → uploads image → publishes to LinkedIn with image.
On Reject: updates Google Sheets → regenerates a new post → sends for approval again.

Usage:
  python3 bot.py          # Run the bot (keeps running until stopped)
  Ctrl+C to stop
"""
from __future__ import annotations

import asyncio
import logging
import os
from datetime import date, datetime
from pathlib import Path

from dotenv import load_dotenv
load_dotenv()

import httpx

from src.utils import setup_logging
from src.search_client import YouSearchClient
from src.llm_client import LLMClient
from src.researcher import research_theme, build_research_summary
from src.post_generator import generate_post
from src.sheets_client import SheetsClient
from src.linkedin_publisher import publish_post
from src.image_generator import generate_image, generate_branded_image
from src import telegram_bot

OUTPUT_DIR = Path(__file__).parent / "output" / "images"

logger = setup_logging("bot")

# In-memory lock to prevent double-processing the same row
_processing_rows: set[int] = set()
_processed_rows: set[int] = set()


async def _regenerate_post(sheets: SheetsClient, theme: str, category: str, row: int):
    """Regenerate a rejected post with a different angle and send for approval."""
    logger.info("Regenerating post for: %s", theme)
    await telegram_bot.send_notification(f"Regenerating post for: {theme}...")

    search = YouSearchClient()
    llm = LLMClient()

    try:
        settings = sheets.get_settings()
        today = date.today()
        weekday = today.strftime("%A")

        # Research
        data = await research_theme(theme, search, category=category)
        summary = build_research_summary(data)

        # Get prior posts for context
        prior_posts = sheets.get_prior_posts(limit=5)
        prior_texts = [p.get("draft_text", "") for p in prior_posts if p.get("draft_text")]

        # Generate with instruction to take a different angle
        draft = await generate_post(
            llm=llm,
            theme=theme,
            day=today.isoformat(),
            weekday=weekday,
            settings=settings,
            research_summary=summary + "\n\nIMPORTANT: The previous draft was rejected. Take a COMPLETELY different angle, structure, and opening.",
            prior_posts_this_week=[],
            prior_published=prior_texts,
        )

        if not draft:
            await telegram_bot.send_notification(f"Failed to regenerate post for: {theme}")
            return

        char_count = len(draft)

        # Generate image
        image_path = await generate_image(theme, category=category)

        # Write new row to Sheets
        post_data = {
            "week_start": today.isoformat(),
            "day": today.isoformat(),
            "theme": theme,
            "draft_text": draft,
            "char_count": char_count,
            "research_summary": summary[:500],
            "status": "pending_approval",
            "suggested_time": "09:00 UTC",
        }
        sheets.append_post(post_data)
        posts_ws = sheets._ws("Posts")
        new_row = len(posts_ws.get_all_values())

        # Send to Telegram with image + buttons
        msg_id = await telegram_bot.send_draft(
            day=today.isoformat(),
            weekday=weekday,
            theme=theme,
            draft_text=draft,
            char_count=char_count,
            suggested_time="09:00 UTC",
            row_number=new_row,
            image_path=image_path,
        )
        if msg_id:
            sheets.update_post_status(new_row, "pending_approval", telegram_msg_id=msg_id)

        logger.info("Regenerated post at row %d", new_row)

    finally:
        await search.close()
        await llm.close()


async def handle_callback(callback: dict, sheets: SheetsClient):
    """Process a single Approve/Reject callback."""
    callback_id = callback["id"]
    data = callback.get("data", "")
    user = callback.get("from", {}).get("first_name", "Unknown")

    parsed = telegram_bot.parse_callback_data(data)
    if not parsed:
        await telegram_bot.answer_callback(callback_id, "Unknown action")
        return

    action = parsed["action"]
    row = parsed["row"]
    logger.info("%s clicked %s for row %d", user, action, row)

    # Get post data from Sheets
    ws = sheets._ws("Posts")
    all_rows = ws.get_all_values()
    if row > len(all_rows):
        await telegram_bot.answer_callback(callback_id, "Row not found!")
        return

    post_row = all_rows[row - 1]
    draft_text = post_row[3] if len(post_row) > 3 else ""
    theme = post_row[2] if len(post_row) > 2 else "unknown"

    if action == "approve":
        # Prevent double-processing
        if row in _processing_rows or row in _processed_rows:
            await telegram_bot.answer_callback(callback_id, "Already processing or published!")
            return

        current_status = post_row[6] if len(post_row) > 6 else ""
        if current_status.strip().lower() in ("published", "publishing"):
            await telegram_bot.answer_callback(callback_id, "Already published!")
            return

        _processing_rows.add(row)
        sheets.update_post_status(row, "publishing")
        await telegram_bot.answer_callback(callback_id, "Approved! Publishing now...")

        if not draft_text:
            await telegram_bot.send_notification(f"Row {row} has no draft text!")
            return

        # Generate AI image
        logger.info("Generating image for row %d...", row)
        category_val = ""
        themes_data = sheets.get_active_themes()
        for t in themes_data:
            if t["theme"] == theme:
                category_val = t.get("category", "")
                break
        image_path = await generate_image(theme, category=category_val)

        # Publish to LinkedIn with image
        logger.info("Publishing row %d to LinkedIn with image...", row)
        result = await publish_post(draft_text, image_path=image_path)

        if result["success"]:
            sheets.update_post_status(
                row, "published",
                linkedin_post_id=result["post_id"],
                published_at=datetime.now().isoformat(),
            )
            await telegram_bot.send_notification(
                f"Published to LinkedIn with image!\n"
                f"Theme: {theme}\n"
                f"Post ID: {result['post_id']}"
            )
            logger.info("Row %d published: %s", row, result["post_id"])
            _processed_rows.add(row)
        else:
            sheets.update_post_status(row, "approved", feedback=f"Publish failed: {result['error']}")
            await telegram_bot.send_notification(f"Failed to publish row {row}: {result['error']}")
            logger.error("Row %d publish failed: %s", row, result["error"])
        _processing_rows.discard(row)

    elif action == "reject":
        sheets.update_post_status(row, "rejected", feedback="Rejected via Telegram")
        await telegram_bot.answer_callback(callback_id, "Rejected! Generating new version...")

        # Get category from Theme Bank for image generation
        themes_data = sheets.get_active_themes()
        category = ""
        for t in themes_data:
            if t["theme"] == theme:
                category = t.get("category", "")
                break

        # Regenerate with different angle
        await _regenerate_post(sheets, theme, category, row)


async def run_bot():
    """Long-polling bot that handles callbacks in real-time."""
    logger.info("=== LinkedIn Post Scheduler Bot Started ===")
    logger.info("Listening for Approve/Reject button clicks...")
    logger.info("Press Ctrl+C to stop.\n")

    sheets = SheetsClient()
    offset = 0

    while True:
        try:
            bot_token = os.getenv("TELEGRAM_BOT_TOKEN", "")
            url = f"https://api.telegram.org/bot{bot_token}/getUpdates"

            payload = {
                "offset": offset,
                "timeout": 30,
                "allowed_updates": ["callback_query"],
            }

            async with httpx.AsyncClient(timeout=40) as client:
                resp = await client.post(url, json=payload)

                if resp.status_code != 200:
                    logger.error("getUpdates failed: %d", resp.status_code)
                    await asyncio.sleep(5)
                    continue

                updates = resp.json().get("result", [])

            for update in updates:
                update_id = update["update_id"]
                offset = update_id + 1

                callback = update.get("callback_query")
                if callback:
                    await handle_callback(callback, sheets)

        except KeyboardInterrupt:
            logger.info("\nBot stopped.")
            break
        except Exception as e:
            logger.error("Bot error: %s", e)
            await asyncio.sleep(5)


PID_FILE = Path(__file__).parent / ".bot.pid"


def _check_and_write_pid():
    """Ensure only one bot instance runs. Kill old one if found."""
    if PID_FILE.exists():
        old_pid = int(PID_FILE.read_text().strip())
        try:
            os.kill(old_pid, 0)  # Check if process exists
            # Old process is still running — kill it
            logger.info("Killing old bot process (PID %d)...", old_pid)
            os.kill(old_pid, 9)
            import time
            time.sleep(1)
        except ProcessLookupError:
            pass  # Old process already dead
    PID_FILE.write_text(str(os.getpid()))


def _cleanup_pid():
    if PID_FILE.exists():
        PID_FILE.unlink(missing_ok=True)


def main():
    _check_and_write_pid()
    try:
        asyncio.run(run_bot())
    except KeyboardInterrupt:
        print("\nBot stopped.")
    finally:
        _cleanup_pid()


if __name__ == "__main__":
    main()
