#!/usr/bin/env python3
"""Webhook server for Telegram approve/reject callbacks.

Designed for Google Cloud Run — sleeps when idle, wakes on POST.
Handles the same approve/reject logic as poll_approvals.py but via webhook.

Usage:
  python webhook_server.py                    # Run locally on port 8080
  PORT=8080 python webhook_server.py          # Custom port

Deploy to Cloud Run, then set Telegram webhook:
  python webhook_server.py --set-webhook URL
"""
from __future__ import annotations

import argparse
import asyncio
import json
from pathlib import Path
import logging
import os
from datetime import date, datetime
from http.server import HTTPServer, BaseHTTPRequestHandler

from dotenv import load_dotenv
load_dotenv()

from src.utils import setup_logging
from src.search_client import YouSearchClient
from src.llm_client import LLMClient
from src.researcher import research_theme, build_research_summary
from src.post_generator import generate_post
from src.sheets_client import SheetsClient
from src.linkedin_publisher import publish_post
from src.image_generator import generate_image
from src.comment_replier import reply_to_comment
from src import telegram_bot

logger = setup_logging("webhook")


async def handle_approve(sheets: SheetsClient, row: int, callback_id: str):
    """Approve → generate AI image → publish to LinkedIn."""
    ws = sheets._ws("Posts")
    all_rows = ws.get_all_values()
    if row > len(all_rows):
        await telegram_bot.answer_callback(callback_id, "Row not found!")
        return

    post_row = all_rows[row - 1]
    draft_text = post_row[3] if len(post_row) > 3 else ""
    theme = post_row[2] if len(post_row) > 2 else "unknown"
    current_status = post_row[6] if len(post_row) > 6 else ""

    if current_status.strip().lower() == "published":
        await telegram_bot.answer_callback(callback_id, "Already published!")
        return

    sheets.update_post_status(row, "publishing")
    await telegram_bot.answer_callback(callback_id, "Approved! Publishing now...")

    if not draft_text:
        await telegram_bot.send_notification(f"Row {row} has no draft text!")
        return

    try:
        # Get category for AI image
        themes_data = sheets.get_active_themes()
        category = ""
        for t in themes_data:
            if t["theme"] == theme:
                category = t.get("category", "")
                break

        # Check if this is a carousel or video post (research_summary contains JSON)
        import json
        from src.carousel_generator import generate_carousel_pdf
        from src.linkedin_publisher import download_youtube_video
        research_summary = post_row[5] if len(post_row) > 5 else ""
        carousel_path = None
        video_path = None
        try:
            research_data = json.loads(research_summary)
            if "carousel" in research_data:
                carousel_content = research_data["carousel"]
                logger.info("Carousel data found — generating PDF for row %d...", row)
                carousel_path = generate_carousel_pdf(
                    hook=carousel_content["hook"],
                    points=carousel_content["points"],
                    cta_question=carousel_content.get("cta_question", "What do you think?"),
                    category=category,
                )
                logger.info("Carousel PDF generated: %s", carousel_path)
            elif "video_url" in research_data:
                video_url = research_data["video_url"]
                logger.info("Downloading video via Apify for row %d...", row)
                video_path = download_youtube_video(video_url)
                if video_path:
                    logger.info("Video ready: %s", video_path)
                else:
                    logger.warning("Video download failed, will use image")
        except (json.JSONDecodeError, KeyError):
            pass  # Not a carousel/video post

        # Only generate image if no video (video posts = text + video only)
        image_path = None
        if not video_path:
            logger.info("Generating image for row %d...", row)
            image_path = await generate_image(theme, category=category)
            logger.info("Image generated: %s", image_path)

        # Publish to LinkedIn (video > carousel > image)
        logger.info("Publishing row %d to LinkedIn...", row)
        result = await publish_post(draft_text, image_path=image_path, document_path=carousel_path, video_path=video_path)
    except Exception as e:
        logger.error("Publish pipeline error for row %d: %s", row, e)
        sheets.update_post_status(row, "approved", feedback=f"Publish error: {e}")
        await telegram_bot.send_notification(f"Publish error for row {row}: {e}")
        return

    if result["success"]:
        sheets.update_post_status(
            row, "published",
            linkedin_post_id=result["post_id"],
            published_at=datetime.now().isoformat(),
        )
        await telegram_bot.send_notification(
            f"Published to LinkedIn!\n"
            f"Theme: {theme}\n"
            f"Post ID: {result['post_id']}"
        )
        logger.info("Row %d published: %s", row, result["post_id"])
    else:
        sheets.update_post_status(row, "approved", feedback=f"Publish failed: {result['error']}")
        await telegram_bot.send_notification(f"Failed to publish row {row}: {result['error']}")
        logger.error("Row %d publish failed: %s", row, result["error"])


async def handle_reject(sheets: SheetsClient, row: int, callback_id: str):
    """Reject → regenerate with different angle → send to Telegram."""
    ws = sheets._ws("Posts")
    all_rows = ws.get_all_values()
    if row > len(all_rows):
        await telegram_bot.answer_callback(callback_id, "Row not found!")
        return

    post_row = all_rows[row - 1]
    theme = post_row[2] if len(post_row) > 2 else "unknown"

    sheets.update_post_status(row, "rejected", feedback="Rejected via Telegram")
    await telegram_bot.answer_callback(callback_id, "Rejected! Regenerating...")

    themes_data = sheets.get_active_themes()
    category = ""
    for t in themes_data:
        if t["theme"] == theme:
            category = t.get("category", "")
            break

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


def _extract_url_from_message(msg_text: str) -> str:
    """Extract LinkedIn URL from Telegram message text."""
    import re
    # Try URL: prefix first
    for line in msg_text.split("\n"):
        line = line.strip()
        if line.startswith("URL:"):
            return line.replace("URL:", "").strip()
    # Fallback: find any LinkedIn URL in the message
    match = re.search(r'https://www\.linkedin\.com/feed/update/urn:li:activity:\d+/?', msg_text)
    if match:
        return match.group(0)
    return ""


async def handle_comment_approve(msg_text: str, callback_id: str):
    """Approve a comment → find in sheet by URL → post on LinkedIn."""
    await telegram_bot.answer_callback(callback_id, "Posting comment...")

    url = _extract_url_from_message(msg_text)
    if not url:
        await telegram_bot.send_notification("Could not extract URL from message")
        return

    try:
        sheets = SheetsClient()
        ws = sheets._spreadsheet.worksheet("CommentQueue")
        rows = ws.get_all_values()

        # Find matching pending comment by URL (partial match for truncated Telegram messages)
        item = None
        for i, row in enumerate(rows[1:], start=2):
            if len(row) >= 4 and row[3].strip().lower() in ("pending", "failed"):
                row_url = row[0].strip()
                if row_url == url or url in row_url or row_url in url:
                    item = {"row_num": i, "url": row_url, "comment": row[1], "author": row[2]}
                    break

        if not item:
            await telegram_bot.send_notification(f"Comment not found in queue for: {url[:60]}")
            logger.error("No match. URL from Telegram: [%s]", url)
            return

        logger.info("Posting comment on: %s", item["url"][:60])

        from src.commenter.poster import post_comment
        success = await post_comment(item["url"], item["comment"])

        if success:
            ws.update_cell(item["row_num"], 4, "posted")
            await telegram_bot.send_notification(f"Comment posted on {item['author']}'s post!")
            logger.info("Comment posted successfully")
        else:
            ws.update_cell(item["row_num"], 4, "failed")
            await telegram_bot.send_notification(f"Failed to post comment on {item['author']}'s post")
            logger.error("Comment posting failed")

    except Exception as e:
        logger.error("Comment approve error: %s", e)
        await telegram_bot.send_notification(f"Comment error: {e}")


async def handle_comment_skip(msg_text: str, callback_id: str):
    """Skip a comment → mark as skipped in sheet."""
    await telegram_bot.answer_callback(callback_id, "Skipped")

    url = _extract_url_from_message(msg_text)
    if not url:
        return

    try:
        sheets = SheetsClient()
        ws = sheets._spreadsheet.worksheet("CommentQueue")
        rows = ws.get_all_values()

        for i, row in enumerate(rows[1:], start=2):
            if len(row) >= 4 and row[3].strip().lower() == "pending":
                row_url = row[0].strip()
                if row_url == url or url in row_url or row_url in url:
                    ws.update_cell(i, 4, "skipped")
                    logger.info("Skipped comment for: %s", row_url[:60])
                    break
    except Exception as e:
        logger.warning("Skip error: %s", e)


async def process_update(update: dict):
    """Process a single Telegram update."""
    callback = update.get("callback_query")
    if not callback:
        return

    callback_id = callback["id"]
    data = callback.get("data", "")
    user = callback.get("from", {}).get("first_name", "Unknown")

    # Handle comment approve/skip
    if data.startswith("cmt_approve_"):
        logger.info("%s approved a comment", user)
        # Extract URL from the Telegram message text
        msg_text = callback.get("message", {}).get("text", "")
        await handle_comment_approve(msg_text, callback_id)
        return
    elif data.startswith("cmt_skip_"):
        # Mark as skipped in sheet
        msg_text = callback.get("message", {}).get("text", "")
        await handle_comment_skip(msg_text, callback_id)
        return

    # Handle post approve/reject
    parsed = telegram_bot.parse_callback_data(data)
    if not parsed:
        await telegram_bot.answer_callback(callback_id, "Unknown action")
        return

    action = parsed["action"]
    row = parsed["row"]
    logger.info("%s clicked %s for row %d", user, action, row)

    sheets = SheetsClient()

    if action == "approve":
        await handle_approve(sheets, row, callback_id)
    elif action == "reject":
        await handle_reject(sheets, row, callback_id)


class WebhookHandler(BaseHTTPRequestHandler):
    """Handle incoming Telegram webhook POST requests."""

    def do_POST(self):
        from urllib.parse import urlparse
        path = urlparse(self.path).path
        content_length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(content_length)

        # Cookie update endpoint
        if path == "/update-cookies":
            try:
                data = json.loads(body)
                cookies = data.get("cookies", [])
                cookie_path = Path("/app/linkedin_cookies_render.json")
                cookie_path.write_text(json.dumps(cookies))
                logger.info("Updated Render cookies: %d cookies saved", len(cookies))

                self.send_response(200)
                self.send_header("Content-Type", "text/plain")
                self.end_headers()
                self.wfile.write(f"Saved {len(cookies)} cookies".encode())
            except Exception as e:
                self.send_response(500)
                self.send_header("Content-Type", "text/plain")
                self.end_headers()
                self.wfile.write(f"Error: {e}".encode())
            return

        # Telegram webhook
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(b'{"ok": true}')

        try:
            update = json.loads(body)
            asyncio.run(process_update(update))
        except Exception as e:
            logger.error("Webhook processing error: %s", e)

    def do_GET(self):
        """Health check + login endpoint."""
        from urllib.parse import urlparse, parse_qs
        path = urlparse(self.path).path

        if path == "/login":
            # Login to LinkedIn from Render's IP and save cookies
            self.send_response(200)
            self.send_header("Content-Type", "text/plain")
            self.end_headers()

            try:
                result = asyncio.run(self._linkedin_login())
                self.wfile.write(result.encode())
            except Exception as e:
                self.wfile.write(f"Login failed: {e}".encode())
            return

        if path == "/cookie-status":
            self.send_response(200)
            self.send_header("Content-Type", "text/plain")
            self.end_headers()
            cookie_path = Path("/app/linkedin_cookies_render.json")
            if cookie_path.exists():
                import json as _json
                cookies = _json.loads(cookie_path.read_text())
                self.wfile.write(f"Cookies: {len(cookies)} saved\nFile size: {cookie_path.stat().st_size} bytes".encode())
            else:
                self.wfile.write(b"No cookies saved. Visit /login first.")
            return

        # Default health check
        self.send_response(200)
        self.send_header("Content-Type", "text/plain")
        self.end_headers()
        env_keys = [
            "GOOGLE_SHEETS_CREDENTIALS", "GOOGLE_SHEET_ID",
            "TELEGRAM_BOT_TOKEN", "TELEGRAM_CHAT_ID",
            "LINKEDIN_ACCESS_TOKEN", "LINKEDIN_PERSON_ID",
            "HF_API_KEY", "LINKEDIN_EMAIL", "APIFY_TOKEN",
        ]
        lines = ["LinkedIn Bot Webhook OK\n\nEnv vars:"]
        for k in env_keys:
            val = os.getenv(k, "")
            status = f"{len(val)} chars" if val else "MISSING"
            lines.append(f"  {k}: {status}")

        cookie_path = Path("/app/linkedin_cookies_render.json")
        lines.append(f"\n  Render cookies: {'EXISTS' if cookie_path.exists() else 'MISSING'}")
        self.wfile.write("\n".join(lines).encode())

    @staticmethod
    async def _linkedin_login() -> str:
        """Login to LinkedIn headless from Render's IP."""
        from playwright.async_api import async_playwright

        email = os.getenv("LINKEDIN_EMAIL", "")
        password = os.getenv("LINKEDIN_PASSWORD", "")
        if not email or not password:
            return "LINKEDIN_EMAIL and LINKEDIN_PASSWORD env vars required"

        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            context = await browser.new_context(
                user_agent="Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                viewport={"width": 1280, "height": 800},
            )
            page = await context.new_page()

            await page.goto("https://www.linkedin.com/login", wait_until="networkidle")
            await page.wait_for_timeout(3000)

            # Fill login
            try:
                await page.fill('input#username', email, timeout=10000)
                await page.fill('input#password', password, timeout=10000)
                await page.click('button[type="submit"]', timeout=10000)
            except Exception:
                try:
                    await page.fill('input[name="session_key"]', email, timeout=10000)
                    await page.fill('input[name="session_password"]', password, timeout=10000)
                    await page.click('button[type="submit"]', timeout=10000)
                except Exception as e:
                    await browser.close()
                    return f"Could not fill login form: {e}"

            await page.wait_for_timeout(8000)

            # Check if login succeeded
            current_url = page.url
            title = await page.title()

            if "challenge" in current_url or "checkpoint" in current_url:
                await browser.close()
                return f"CAPTCHA/2FA detected. Login manually and upload cookies.\nURL: {current_url}"

            if "feed" in current_url or "mynetwork" in current_url:
                # Save cookies
                cookies = await context.cookies()
                cookie_path = Path("/app/linkedin_cookies_render.json")
                cookie_path.write_text(json.dumps(cookies))
                await browser.close()
                return f"Login successful! Saved {len(cookies)} cookies.\nPage: {title}"

            await browser.close()
            return f"Login unclear. URL: {current_url}, Title: {title}"

    def log_message(self, format, *args):
        """Suppress default access logs."""
        pass


async def set_webhook(url: str):
    """Set Telegram webhook to the given URL."""
    import httpx
    bot_token = os.getenv("TELEGRAM_BOT_TOKEN", "")
    api_url = f"https://api.telegram.org/bot{bot_token}/setWebhook"
    payload = {"url": url, "allowed_updates": ["callback_query"]}

    async with httpx.AsyncClient() as client:
        resp = await client.post(api_url, json=payload)
        if resp.status_code == 200:
            logger.info("Webhook set to: %s", url)
            print(f"Webhook set to: {url}")
        else:
            logger.error("Failed to set webhook: %s", resp.text)
            print(f"Failed: {resp.text}")


def main():
    parser = argparse.ArgumentParser(description="Telegram webhook server")
    parser.add_argument("--set-webhook", metavar="URL", help="Set Telegram webhook URL and exit")
    parser.add_argument("--port", type=int, default=int(os.getenv("PORT", "8080")), help="Server port")
    args = parser.parse_args()

    if args.set_webhook:
        asyncio.run(set_webhook(args.set_webhook))
        return

    logger.info("Starting webhook server on port %d", args.port)
    server = HTTPServer(("0.0.0.0", args.port), WebhookHandler)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        logger.info("Server stopped")
        server.server_close()


if __name__ == "__main__":
    main()
