#!/usr/bin/env python3
"""Poll Telegram for approval/rejection callbacks, publish approved posts, regenerate rejected ones.

Replaces bot.py — runs as a GitHub Action every 15 minutes. No local setup needed.

On Approve: updates Sheets → generates branded image → publishes to LinkedIn with image
On Reject: updates Sheets → regenerates post with different angle → sends to Telegram again
"""
from __future__ import annotations

import asyncio
import json
import logging
import os
from datetime import date, datetime
from pathlib import Path

from src.utils import setup_logging
from src.search_client import YouSearchClient
from src.llm_client import LLMClient
from src.researcher import research_theme, build_research_summary
from src.post_generator import generate_post
from src.sheets_client import SheetsClient
from src.linkedin_publisher import publish_post
from src.image_generator import generate_branded_image, generate_image
from src import telegram_bot

logger = setup_logging("poll_approvals")

# Track processed callbacks to prevent duplicates
PROCESSED_FILE = Path("/tmp/processed_callbacks.json")


def _load_processed() -> set:
    if PROCESSED_FILE.exists():
        try:
            return set(json.loads(PROCESSED_FILE.read_text()))
        except (json.JSONDecodeError, TypeError):
            pass
    return set()


def _save_processed(processed: set):
    PROCESSED_FILE.write_text(json.dumps(list(processed)))


async def _handle_approve(sheets: SheetsClient, row: int, callback_id: str):
    """Approve → generate image → publish to LinkedIn."""
    # Get post data from Sheets
    ws = sheets._ws("Posts")
    all_rows = ws.get_all_values()
    if row > len(all_rows):
        await telegram_bot.answer_callback(callback_id, "Row not found!")
        return

    post_row = all_rows[row - 1]
    draft_text = post_row[3] if len(post_row) > 3 else ""
    theme = post_row[2] if len(post_row) > 2 else "unknown"
    current_status = post_row[6] if len(post_row) > 6 else ""

    # Skip if already published
    if current_status.strip().lower() in ("published", "publishing"):
        await telegram_bot.answer_callback(callback_id, "Already published!")
        return

    sheets.update_post_status(row, "publishing")
    await telegram_bot.answer_callback(callback_id, "Approved! Publishing now...")

    if not draft_text:
        await telegram_bot.send_notification(f"Row {row} has no draft text!")
        return

    # Generate branded image
    logger.info("Generating image for row %d...", row)
    image_path = generate_branded_image(theme=theme)

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
    else:
        sheets.update_post_status(row, "approved", feedback=f"Publish failed: {result['error']}")
        await telegram_bot.send_notification(f"Failed to publish row {row}: {result['error']}")
        logger.error("Row %d publish failed: %s", row, result["error"])


async def _handle_reject(sheets: SheetsClient, row: int, callback_id: str):
    """Reject → regenerate with different angle → send to Telegram again."""
    ws = sheets._ws("Posts")
    all_rows = ws.get_all_values()
    if row > len(all_rows):
        await telegram_bot.answer_callback(callback_id, "Row not found!")
        return

    post_row = all_rows[row - 1]
    theme = post_row[2] if len(post_row) > 2 else "unknown"

    sheets.update_post_status(row, "rejected", feedback="Rejected via Telegram")
    await telegram_bot.answer_callback(callback_id, "Rejected! Regenerating...")

    # Get category from Theme Bank
    themes_data = sheets.get_active_themes()
    category = ""
    for t in themes_data:
        if t["theme"] == theme:
            category = t.get("category", "")
            break

    # Regenerate
    logger.info("Regenerating post for: %s", theme)
    await telegram_bot.send_notification(f"Regenerating post for: {theme}...")

    search = YouSearchClient()
    llm = LLMClient()

    try:
        settings = sheets.get_settings()
        today = date.today()
        weekday = today.strftime("%A")

        data = await research_theme(theme, search, category=category)
        summary = build_research_summary(data)

        prior_posts = sheets.get_prior_posts(limit=5)
        prior_texts = [p.get("draft_text", "") for p in prior_posts if p.get("draft_text")]

        draft = await generate_post(
            llm=llm, theme=theme, day=today.isoformat(), weekday=weekday,
            settings=settings,
            research_summary=summary + "\n\nIMPORTANT: The previous draft was rejected. Take a COMPLETELY different angle.",
            prior_posts_this_week=[], prior_published=prior_texts,
        )

        if not draft:
            await telegram_bot.send_notification(f"Failed to regenerate post for: {theme}")
            return

        image_path = await generate_image(theme, category=category)

        post_data = {
            "week_start": today.isoformat(), "day": today.isoformat(),
            "theme": theme, "draft_text": draft, "char_count": len(draft),
            "research_summary": summary[:500], "status": "pending_approval",
            "suggested_time": "09:00 UTC",
        }
        sheets.append_post(post_data)
        posts_ws = sheets._ws("Posts")
        new_row = len(posts_ws.get_all_values())

        msg_id = await telegram_bot.send_draft(
            day=today.isoformat(), weekday=weekday, theme=theme,
            draft_text=draft, char_count=len(draft),
            suggested_time="09:00 UTC", row_number=new_row,
            image_path=image_path,
        )
        if msg_id:
            sheets.update_post_status(new_row, "pending_approval", telegram_msg_id=msg_id)

        logger.info("Regenerated post at row %d", new_row)

    finally:
        await search.close()
        await llm.close()


async def run_poll():
    """Poll Telegram for callback queries and process approve/reject/publish."""
    logger.info("=== Polling Telegram for approvals ===")

    processed = _load_processed()
    updates = await telegram_bot.get_updates(offset=0)

    if not updates:
        logger.info("No new callbacks. Done.")
        return

    # Filter out already-processed updates
    new_updates = [u for u in updates if str(u["update_id"]) not in processed]
    if not new_updates:
        logger.info("All updates already processed. Done.")
        return

    logger.info("Found %d new updates", len(new_updates))
    sheets = SheetsClient()

    for update in new_updates:
        update_id = str(update["update_id"])
        processed.add(update_id)

        callback = update.get("callback_query")
        if not callback:
            continue

        callback_id = callback["id"]
        data = callback.get("data", "")
        parsed = telegram_bot.parse_callback_data(data)

        if not parsed:
            await telegram_bot.answer_callback(callback_id, "Unknown action")
            continue

        action = parsed["action"]
        row = parsed["row"]
        user = callback.get("from", {}).get("first_name", "Unknown")
        logger.info("%s clicked %s for row %d", user, action, row)

        if action == "approve":
            await _handle_approve(sheets, row, callback_id)
        elif action == "reject":
            await _handle_reject(sheets, row, callback_id)

    _save_processed(processed)
    logger.info("=== Poll complete ===")


def main():
    asyncio.run(run_poll())


if __name__ == "__main__":
    main()
