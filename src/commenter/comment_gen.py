"""Generate contextual AI comments for LinkedIn posts."""

from __future__ import annotations

import logging
import os
import re

import httpx
from dotenv import load_dotenv

load_dotenv()
logger = logging.getLogger(__name__)


def generate_comment(post_text: str, author: str = "") -> str | None:
    """Generate a comment via the configured LLM (Ollama gemma4 by default, HF optional)."""
    provider = os.getenv("LLM_PROVIDER", "ollama").lower()
    if provider == "hf":
        api_key = os.getenv("HF_API_KEY", "")
        model = os.getenv("HF_MODEL", "Qwen/Qwen3-235B-A22B")
        url = os.getenv("HF_API_URL", "https://router.huggingface.co/v1/chat/completions")
    else:  # ollama (default) — OpenAI-compatible
        api_key = os.getenv("OLLAMA_API_KEY", "") or os.getenv("HF_API_KEY", "")
        model = os.getenv("OLLAMA_MODEL", "gemma4:31b-cloud")
        url = os.getenv("OLLAMA_API_URL", "https://ollama.com/v1/chat/completions")

    if not api_key:
        logger.error("No LLM API key set (OLLAMA_API_KEY / HF_API_KEY)")
        return None

    # Build author instruction based on whether we know the name
    known_author = author and author.lower() not in ("unknown", "")
    if known_author:
        author_instruction = f'- You may mention "{author}" by name if it fits naturally, but don\'t force it'
    else:
        author_instruction = '- Do NOT mention any name or placeholder'

    prompt = f"""You are an Associate Director of Engineering commenting on a LinkedIn post. Write like a real human — natural, conversational, no template.

POST BY: {author if known_author else "the author"}
POST:
{post_text[:800]}

Write a LinkedIn comment (2-3 short paragraphs) that:
{author_instruction}
- Each paragraph is 1-2 sentences MAX
- Put a BLANK LINE between each paragraph
- Add a unique perspective, data point, or counterpoint from your experience
- Reference something SPECIFIC from the post
- Sound like an engineering leader having a conversation, not writing a template
- NO emojis, NO markdown, PLAIN TEXT only
- NEVER write "[author]", "Unknown", or any placeholder
- Do NOT start with generic praise like "Great post" or "Really valuable breakdown"
- Every comment should feel different — vary tone, structure, and opening

Return ONLY the comment text."""

    system_msg = "Write concise LinkedIn comments."
    if "qwen" in model.lower():
        system_msg += " /no_think"
    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": system_msg},
            {"role": "user", "content": prompt},
        ],
        "max_tokens": 300,
        "temperature": 0.7,
    }
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}

    try:
        resp = httpx.post(url, json=payload, headers=headers, timeout=60)
        if resp.status_code == 200:
            text = resp.json()["choices"][0]["message"]["content"].strip()
            text = re.sub(r"<think>.*?</think>", "", text, flags=re.DOTALL).strip()
            text = re.sub(r'\*\*(.+?)\*\*', r'\1', text)
            text = re.sub(r'\*(.+?)\*', r'\1', text)
            logger.info("Comment generated: %d chars", len(text))
            return text
        else:
            logger.error("LLM error %d: %s", resp.status_code, resp.text[:200])
            return None
    except Exception as e:
        logger.error("LLM exception: %s", e)
        return None
