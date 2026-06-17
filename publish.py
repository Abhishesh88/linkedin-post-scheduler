#!/usr/bin/env python3
"""Publish approved LinkedIn posts scheduled for today.

Designed to run weekdays at 09:00 UTC via GitHub Actions.
"""

import asyncio
import logging
from datetime import date, datetime

from src.utils import setup_logging
from src.sheets_client import SheetsClient
from src.linkedin_publisher import publish_post
from src import telegram_bot

logger = setup_logging("publish")


async def run_publish():
    """Find approved posts for today and publish to LinkedIn."""
    today = date.today().isoformat()
    logger.info("=== Publishing posts for %s ===", today)

    sheets = SheetsClient()
    approved = sheets.get_posts_by_status("approved")

    # Filter to today's posts
    todays_posts = [p for p in approved if p.get("day", "") == today]

    if not todays_posts:
        logger.info("No approved posts scheduled for today. Done.")
        return

    logger.info("Found %d approved posts for today", len(todays_posts))

    published = 0
    for post in todays_posts:
        row = post["_row"]
        draft = post.get("draft_text", "")
        theme = post.get("theme", "unknown")

        if not draft:
            logger.warning("Row %d has no draft text. Skipping.", row)
            continue

        logger.info("Publishing row %d: %s", row, theme)
        result = await publish_post(draft)

        if result["success"]:
            sheets.update_post_status(
                row, "published",
                linkedin_post_id=result["post_id"],
                published_at=datetime.now().isoformat(),
            )
            await telegram_bot.send_notification(f"Published: {theme} (row {row})")
            published += 1
            logger.info("Published row %d: %s", row, result["post_id"])
        else:
            logger.error("Failed to publish row %d: %s", row, result["error"])
            await telegram_bot.send_notification(f"FAILED to publish row {row}: {result['error']}")

    logger.info("=== Publish complete: %d/%d posted ===", published, len(todays_posts))


def main():
    asyncio.run(run_publish())


if __name__ == "__main__":
    main()
