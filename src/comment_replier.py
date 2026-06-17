"""Reply to comments on your own LinkedIn posts via API."""

from __future__ import annotations

import logging
import os
import re

import httpx
from dotenv import load_dotenv

load_dotenv()
logger = logging.getLogger(__name__)

LINKEDIN_API_BASE = "https://api.linkedin.com/rest"
API_VERSION = "202502"


def _headers() -> dict:
    return {
        "Authorization": f"Bearer {os.getenv('LINKEDIN_ACCESS_TOKEN', '')}",
        "Content-Type": "application/json",
        "X-Restli-Protocol-Version": "2.0.0",
        "LinkedIn-Version": API_VERSION,
    }


def _person_urn() -> str:
    return f"urn:li:person:{os.getenv('LINKEDIN_PERSON_ID', '')}"


async def get_post_comments(activity_urn: str) -> list[dict]:
    """Fetch comments on a LinkedIn post using REST API."""
    encoded_urn = activity_urn.replace(":", "%3A")
    endpoint = f"{LINKEDIN_API_BASE}/socialActions/{encoded_urn}/comments?count=20"
    try:
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.get(endpoint, headers=_headers())
            if resp.status_code == 200:
                data = resp.json()
                comments = []
                my_urn = _person_urn()
                for elem in data.get("elements", []):
                    actor = elem.get("actor", "")
                    # Skip our own comments
                    if actor == my_urn:
                        continue
                    comment_urn = elem.get("$URN", elem.get("commentUrn", ""))
                    text = elem.get("message", {}).get("text", "")
                    if text and comment_urn:
                        comments.append({
                            "comment_urn": comment_urn,
                            "activity_urn": activity_urn,
                            "actor": actor,
                            "text": text,
                        })
                return comments
            else:
                logger.error("Fetch comments failed %d: %s", resp.status_code, resp.text[:200])
                return []
    except Exception as e:
        logger.error("Fetch comments error: %s", e)
        return []


async def reply_to_comment(activity_urn: str, parent_comment_urn: str, reply_text: str) -> bool:
    """Reply to a specific comment on a LinkedIn post."""
    encoded_urn = activity_urn.replace(":", "%3A")
    endpoint = f"{LINKEDIN_API_BASE}/socialActions/{encoded_urn}/comments"
    payload = {
        "actor": _person_urn(),
        "object": activity_urn,
        "parentComment": parent_comment_urn,
        "message": {
            "text": reply_text,
        },
    }

    try:
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.post(endpoint, json=payload, headers=_headers())
            if resp.status_code in (200, 201):
                logger.info("Replied to comment %s", parent_comment_urn[:50])
                return True
            else:
                logger.error("Reply failed %d: %s", resp.status_code, resp.text[:300])
                return False
    except Exception as e:
        logger.error("Reply error: %s", e)
        return False


def generate_reply(comment_text: str, post_text: str) -> str | None:
    """Generate a reply to a comment using LLM."""
    hf_key = os.getenv("HF_API_KEY", "")
    hf_model = os.getenv("HF_MODEL", "Qwen/Qwen3.5-122B-A10B")
    hf_url = os.getenv("HF_API_URL", "https://router.huggingface.co/v1/chat/completions")

    if not hf_key:
        return None

    prompt = f"""You are replying to a comment on your LinkedIn post. Write a short, natural reply.

YOUR POST:
{post_text[:500]}

THEIR COMMENT:
{comment_text}

RULES:
- 1-3 sentences max
- Be genuine and conversational
- Add value — share an insight, ask a follow-up question, or acknowledge their point
- Sound like a real person, not a bot
- NO emojis, NO markdown, PLAIN TEXT only
- Do NOT start with "Great point" or "Thanks for sharing"

Return ONLY the reply text."""

    payload = {
        "model": hf_model,
        "messages": [
            {"role": "system", "content": "Write short, natural LinkedIn comment replies. /no_think"},
            {"role": "user", "content": prompt},
        ],
        "max_tokens": 150,
        "temperature": 0.7,
    }
    headers = {"Authorization": f"Bearer {hf_key}", "Content-Type": "application/json"}

    try:
        resp = httpx.post(hf_url, json=payload, headers=headers, timeout=60)
        if resp.status_code == 200:
            text = resp.json()["choices"][0]["message"]["content"].strip()
            text = re.sub(r"<think>.*?</think>", "", text, flags=re.DOTALL).strip()
            text = re.sub(r'\*\*(.+?)\*\*', r'\1', text)
            text = re.sub(r'\*(.+?)\*', r'\1', text)
            return text
        else:
            logger.error("LLM error %d: %s", resp.status_code, resp.text[:200])
            return None
    except Exception as e:
        logger.error("LLM error: %s", e)
        return None
