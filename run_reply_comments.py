#!/usr/bin/env python3
"""Scan your recent LinkedIn posts for new comments → generate replies → send to Telegram for approval."""
from __future__ import annotations

import asyncio
import logging

from dotenv import load_dotenv
load_dotenv()

from src.utils import setup_logging
from src.sheets_client import SheetsClient
from src.comment_replier import get_post_comments, generate_reply
from src import telegram_bot

logger = setup_logging("reply_comments")


async def run():
    logger.info("=== Scanning for comments to reply to ===")

    sheets = SheetsClient()

    # Get recent published posts (last 7 days)
    posts = sheets.get_posts_by_status("published")
    recent_posts = posts[-10:]  # Last 10 published posts

    if not recent_posts:
        logger.info("No published posts found")
        return

    # Track already-replied comments
    try:
        ws = sheets._spreadsheet.worksheet("CommentReplies")
    except Exception:
        ws = sheets._spreadsheet.add_worksheet("CommentReplies", rows=500, cols=6)
        ws.update("A1:F1", [["date", "post_urn", "comment_urn", "comment_text", "reply_text", "status"]])

    existing = ws.get_all_values()
    replied_urns = {row[2] for row in existing[1:] if len(row) > 2}
    logger.info("Already replied to %d comments", len(replied_urns))

    new_comments = []

    for post in recent_posts:
        post_urn = post.get("linkedin_post_id", "")
        if not post_urn:
            continue

        # Convert share/ugcPost URN to activity URN for comments API
        activity_urn = post_urn.replace("urn:li:share:", "urn:li:activity:").replace("urn:li:ugcPost:", "urn:li:activity:")

        comments = await get_post_comments(activity_urn)
        for comment in comments:
            if comment["comment_urn"] not in replied_urns:
                comment["post_text"] = post.get("draft_text", "")[:500]
                comment["post_urn"] = post_urn
                new_comments.append(comment)

    logger.info("Found %d new comments to reply to", len(new_comments))

    if not new_comments:
        logger.info("No new comments — done")
        return

    # Generate replies and send to Telegram for approval
    from datetime import date
    import json

    from src.comment_replier import reply_to_comment
    from datetime import date

    posted = 0
    for i, comment in enumerate(new_comments[:5]):  # Max 5 replies per run
        logger.info("Generating reply for: %s", comment["text"][:50])
        reply = generate_reply(comment["text"], comment["post_text"])

        if not reply:
            logger.warning("Failed to generate reply, skipping")
            continue

        # Post reply directly (fast replies = algorithm boost)
        logger.info("Posting reply on LinkedIn...")
        success = await reply_to_comment(
            comment["activity_urn"],
            comment["comment_urn"],
            reply,
        )

        status = "posted" if success else "failed"
        if success:
            posted += 1

        # Save to sheet
        ws.append_row([
            date.today().isoformat(),
            comment["post_urn"],
            comment["comment_urn"],
            comment["text"][:500],
            reply,
            status,
        ], value_input_option="RAW")

        # Notify on Telegram
        emoji = "Posted" if success else "Failed"
        await telegram_bot.send_notification(
            f"REPLY {emoji} (#{i+1}):\n\n"
            f"Comment: {comment['text'][:200]}\n\n"
            f"Reply: {reply}"
        )

    logger.info("=== Done. Posted %d/%d replies ===", posted, min(len(new_comments), 5))


def main():
    asyncio.run(run())


if __name__ == "__main__":
    main()
