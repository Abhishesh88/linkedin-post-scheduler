#!/usr/bin/env python3
"""LinkedIn commenting pipeline for GitHub Actions.

Scan → Generate → Send to Telegram with approve/skip buttons.
Approved comments are posted via the Render webhook.
"""
from __future__ import annotations

import asyncio
import json
import logging
import os

from dotenv import load_dotenv
load_dotenv()

from src.utils import setup_logging
from src.commenter.scanner import scan_all_targets, load_state, save_state
from src.commenter.comment_gen import generate_comment
from src import telegram_bot

logger = setup_logging("commenter")


async def run():
    logger.info("=== LinkedIn Commenter Pipeline ===")

    # 1. Scan target creators
    posts = await scan_all_targets()
    if not posts:
        logger.info("No new posts to comment on. Done.")
        return

    logger.info("Found %d new posts to comment on", len(posts))

    # 2. Generate comments
    drafts = []
    for post in posts[:5]:  # Max 5 per run
        logger.info("Generating comment for: %s — %s", post["author"], post["text"][:50])
        comment = generate_comment(post["text"], post["author"])
        if comment:
            drafts.append({"post": post, "comment": comment})

    if not drafts:
        logger.info("No comments generated. Done.")
        return

    # 3. Send to Telegram with approve/skip buttons
    for i, draft in enumerate(drafts):
        post = draft["post"]
        comment = draft["comment"]

        text = (
            f"Comment Draft {i + 1}/{len(drafts)}\n\n"
            f"Post by: {post['author']}\n"
            f"Post: {post['text'][:200]}...\n\n"
            f"---\n"
            f"Your comment:\n{comment}\n"
            f"---\n"
            f"URL: {post['url']}"
        )

        keyboard = {
            "inline_keyboard": [[
                {"text": "Approve & Post", "callback_data": f"cmt_approve_{i}"},
                {"text": "Skip", "callback_data": f"cmt_skip_{i}"},
            ]]
        }

        # Store draft data in callback for webhook to use
        import httpx
        token = os.getenv("TELEGRAM_BOT_TOKEN", "")
        chat_id = os.getenv("TELEGRAM_CHAT_ID", "")

        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.post(
                f"https://api.telegram.org/bot{token}/sendMessage",
                json={"chat_id": chat_id, "text": text, "reply_markup": keyboard},
            )
            if resp.status_code == 200:
                msg_id = resp.json()["result"]["message_id"]
                logger.info("Sent draft %d to Telegram: msg_id=%d", i + 1, msg_id)

    # 4. Save pending drafts for webhook to process on approve
    pending = [{"url": d["post"]["url"], "comment": d["comment"], "author": d["post"]["author"]} for d in drafts]
    pending_path = os.path.join(os.path.dirname(__file__), "src", "commenter", "pending_comments.json")
    with open(pending_path, "w") as f:
        json.dump(pending, f, indent=2)

    # Also store in Google Sheets for Render to access
    from src.sheets_client import SheetsClient
    sheets = SheetsClient()
    try:
        ws = sheets._spreadsheet.worksheet("CommentQueue")
    except Exception:
        # Create the worksheet if it doesn't exist
        ws = sheets._spreadsheet.add_worksheet("CommentQueue", rows=100, cols=4)
        ws.update("A1:D1", [["url", "comment", "author", "status"]])

    # Append pending comments
    for d in pending:
        ws.append_row([d["url"], d["comment"], d["author"], "pending"], value_input_option="RAW")

    logger.info("Saved %d pending comments to CommentQueue sheet", len(pending))
    logger.info("=== Done. Approve in Telegram → Render will post. ===")


def main():
    asyncio.run(run())


if __name__ == "__main__":
    main()
