"""Post comments on LinkedIn using the official Comments API."""

from __future__ import annotations

import logging
import os
import re

import httpx
from dotenv import load_dotenv

load_dotenv()
logger = logging.getLogger(__name__)

LINKEDIN_API_BASE = "https://api.linkedin.com/v2"


def _headers() -> dict:
    return {
        "Authorization": f"Bearer {os.getenv('LINKEDIN_ACCESS_TOKEN', '')}",
        "Content-Type": "application/json",
    }


def _extract_activity_urn(url: str) -> str | None:
    """Extract activity URN from LinkedIn post URL."""
    match = re.search(r'urn:li:activity:(\d+)', url)
    if match:
        return f"urn:li:activity:{match.group(1)}"
    return None


async def post_comment(url: str, comment: str) -> bool:
    """Post a comment on a LinkedIn post using the Comments API.

    No Playwright, no cookies — uses the same LinkedIn API token
    that publishes posts.
    """
    person_id = os.getenv("LINKEDIN_PERSON_ID", "")
    token = os.getenv("LINKEDIN_ACCESS_TOKEN", "")

    if not person_id or not token:
        logger.error("Missing LINKEDIN_ACCESS_TOKEN or LINKEDIN_PERSON_ID")
        return False

    activity_urn = _extract_activity_urn(url)
    if not activity_urn:
        logger.error("Could not extract activity URN from URL: %s", url[:60])
        return False

    endpoint = f"{LINKEDIN_API_BASE}/socialActions/{activity_urn}/comments"
    payload = {
        "actor": f"urn:li:person:{person_id}",
        "object": activity_urn,
        "message": {
            "text": comment,
        },
    }

    try:
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.post(endpoint, json=payload, headers=_headers())

            if resp.status_code in (200, 201):
                comment_id = resp.headers.get("x-restli-id", "")
                logger.info("Comment posted via API on %s (id: %s)", url[:60], comment_id)
                return True
            else:
                logger.error("Comment API error %d: %s", resp.status_code, resp.text[:300])
                return False

    except Exception as e:
        logger.error("Comment API exception: %s", e)
        return False
