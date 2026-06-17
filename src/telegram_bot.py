"""Telegram integration — send drafts with inline buttons, poll for callbacks."""

from __future__ import annotations

import json
import logging
import os

import httpx
from dotenv import load_dotenv

load_dotenv()
logger = logging.getLogger(__name__)


def _bot_token() -> str:
    return os.getenv("TELEGRAM_BOT_TOKEN", "")


def _chat_id() -> str:
    return os.getenv("TELEGRAM_CHAT_ID", "")


def _api_url(method: str) -> str:
    return f"https://api.telegram.org/bot{_bot_token()}/{method}"


def format_draft_message(
    day: str, weekday: str, theme: str, draft_text: str, char_count: int, suggested_time: str,
) -> str:
    """Format a draft post for Telegram display."""
    return (
        f"LinkedIn Draft -- {weekday}, {day}\n"
        f"Theme: {theme}\n\n"
        f"---\n{draft_text}\n---\n\n"
        f"{char_count} chars | Scheduled: {suggested_time}"
    )


def parse_callback_data(data: str) -> dict | None:
    """Parse inline button callback data like 'approve_5' or 'reject_12'."""
    parts = data.split("_", 1)
    if len(parts) != 2 or parts[0] not in ("approve", "reject"):
        return None
    try:
        return {"action": parts[0], "row": int(parts[1])}
    except ValueError:
        return None


async def send_draft(
    day: str, weekday: str, theme: str, draft_text: str, char_count: int,
    suggested_time: str, row_number: int, image_path: str | None = None,
) -> int | None:
    """Send a draft post to Telegram with Approve/Reject inline buttons. Returns message_id.

    If image_path is provided, sends the image first, then the text with buttons.
    """
    inline_keyboard = {
        "inline_keyboard": [[
            {"text": "Approve", "callback_data": f"approve_{row_number}"},
            {"text": "Reject", "callback_data": f"reject_{row_number}"},
        ]]
    }

    async with httpx.AsyncClient(timeout=60) as client:
        # Send image first if available
        if image_path and os.path.exists(image_path):
            try:
                with open(image_path, "rb") as f:
                    files = {"photo": (os.path.basename(image_path), f, "image/png")}
                    data = {"chat_id": _chat_id(), "caption": f"Image for: {theme}"}
                    await client.post(_api_url("sendPhoto"), data=data, files=files)
                    logger.info("Sent image to Telegram for: %s", theme[:50])
            except (httpx.ConnectTimeout, httpx.ReadTimeout):
                logger.warning("Telegram image send timed out — skipping image")

        # Send text with approve/reject buttons (with retry)
        text = format_draft_message(day, weekday, theme, draft_text, char_count, suggested_time)
        payload = {
            "chat_id": _chat_id(),
            "text": text,
            "reply_markup": inline_keyboard,
        }
        for attempt in range(3):
            try:
                resp = await client.post(_api_url("sendMessage"), json=payload)
                if resp.status_code == 200:
                    resp_data = resp.json()
                    msg_id = resp_data["result"]["message_id"]
                    logger.info("Sent draft to Telegram: msg_id=%d, row=%d", msg_id, row_number)
                    return msg_id
                else:
                    logger.error("Telegram sendMessage failed: %d %s", resp.status_code, resp.text[:200])
                    return None
            except (httpx.ConnectTimeout, httpx.ReadTimeout, httpx.ConnectError):
                logger.warning("Telegram send_draft timeout (attempt %d/3)", attempt + 1)
        logger.error("Telegram send_draft failed after 3 retries")
        return None


async def send_notification(text: str):
    """Send a plain text notification to Telegram."""
    payload = {"chat_id": _chat_id(), "text": text}
    async with httpx.AsyncClient(timeout=60) as client:
        for attempt in range(3):
            try:
                resp = await client.post(_api_url("sendMessage"), json=payload)
                if resp.status_code != 200:
                    logger.error("Telegram notification failed: %d", resp.status_code)
                return
            except (httpx.ConnectTimeout, httpx.ReadTimeout, httpx.ConnectError):
                logger.warning("Telegram notification timeout (attempt %d/3)", attempt + 1)
        logger.error("Telegram notification failed after 3 retries")


async def send_photo(file_path: str, caption: str = ""):
    """Send a photo to Telegram."""
    async with httpx.AsyncClient(timeout=30) as client:
        with open(file_path, "rb") as f:
            files = {"photo": (os.path.basename(file_path), f, "image/png")}
            data = {"chat_id": _chat_id()}
            if caption:
                data["caption"] = caption[:1024]
            resp = await client.post(_api_url("sendPhoto"), data=data, files=files)
            if resp.status_code == 200:
                logger.info("Sent photo to Telegram: %s", os.path.basename(file_path))
            else:
                logger.error("Telegram sendPhoto failed: %d", resp.status_code)


async def send_document(file_path: str, caption: str = ""):
    """Send a document (PDF) to Telegram."""
    async with httpx.AsyncClient(timeout=30) as client:
        with open(file_path, "rb") as f:
            files = {"document": (os.path.basename(file_path), f, "application/pdf")}
            data = {"chat_id": _chat_id()}
            if caption:
                data["caption"] = caption[:1024]
            resp = await client.post(_api_url("sendDocument"), data=data, files=files)
            if resp.status_code == 200:
                logger.info("Sent document to Telegram: %s", os.path.basename(file_path))
            else:
                logger.error("Telegram sendDocument failed: %d", resp.status_code)


async def answer_callback(callback_query_id: str, text: str):
    """Answer a Telegram inline button callback."""
    payload = {"callback_query_id": callback_query_id, "text": text}
    async with httpx.AsyncClient() as client:
        await client.post(_api_url("answerCallbackQuery"), json=payload)


async def delete_webhook():
    """Delete any active webhook so getUpdates polling works."""
    async with httpx.AsyncClient(timeout=15) as client:
        # Check if webhook is actually set
        info_resp = await client.post(_api_url("getWebhookInfo"))
        if info_resp.status_code == 200:
            info = info_resp.json().get("result", {})
            webhook_url = info.get("url", "")
            if webhook_url:
                logger.warning("Active webhook found: %s — deleting it", webhook_url)
                await client.post(_api_url("deleteWebhook"))
                logger.info("Webhook deleted")
            else:
                logger.info("No webhook set — getUpdates polling OK")
            pending = info.get("pending_update_count", 0)
            if pending:
                logger.info("Telegram reports %d pending updates", pending)
        else:
            logger.warning("getWebhookInfo failed: %d", info_resp.status_code)


async def get_updates(offset: int = 0) -> list[dict]:
    """Poll for new Telegram updates (callback queries)."""
    payload = {"offset": offset, "timeout": 5, "allowed_updates": ["callback_query"]}
    async with httpx.AsyncClient(timeout=15) as client:
        resp = await client.post(_api_url("getUpdates"), json=payload)
        if resp.status_code == 200:
            data = resp.json()
            results = data.get("result", [])
            logger.info("getUpdates returned %d updates (offset=%d)", len(results), offset)
            for u in results[:3]:
                cb = u.get("callback_query", {})
                logger.info("  update_id=%s, callback_data=%s", u.get("update_id"), cb.get("data", "n/a"))
            return results
        logger.error("Telegram getUpdates failed: %d %s", resp.status_code, resp.text[:200])
        return []
