"""LinkedIn post generation with theme assignment and deduplication."""

from __future__ import annotations

import logging
import random
from datetime import date
from pathlib import Path

from .llm_client import LLMClient, LLMResponse

logger = logging.getLogger(__name__)

PROMPTS_DIR = Path(__file__).parent.parent / "config" / "prompts"


def _load_prompt(name: str) -> str:
    path = PROMPTS_DIR / name
    return path.read_text().strip()


def assign_themes_to_days(themes: list[str], days: list[date]) -> list[tuple[date, str]]:
    """Assign one theme per day. Shuffle, cycle if < 5, never repeat consecutive."""
    pool = list(themes)
    random.shuffle(pool)

    assigned = []
    used_index = 0
    last_theme = None

    for day in days:
        attempts = 0
        while attempts < len(pool):
            candidate = pool[used_index % len(pool)]
            used_index += 1
            attempts += 1
            if candidate != last_theme or len(pool) == 1:
                assigned.append((day, candidate))
                last_theme = candidate
                break
        else:
            candidate = pool[used_index % len(pool)]
            used_index += 1
            assigned.append((day, candidate))
            last_theme = candidate

    return assigned


def format_post_prompt(
    theme: str,
    day: str,
    weekday: str,
    voice: str,
    audience: str,
    cta_style: str,
    hashtags: str,
    research_summary: str,
    prior_posts_this_week: str,
    prior_published: str,
) -> str:
    """Format the user prompt for post generation."""
    template = _load_prompt("post_prompt.txt")
    hashtags_line = f"Approved hashtags: {hashtags}" if hashtags else "No hashtags."
    return template.format(
        theme=theme,
        day=day,
        weekday=weekday,
        voice=voice,
        audience=audience,
        cta_style=cta_style,
        hashtags_line=hashtags_line,
        research_summary=research_summary,
        prior_posts_this_week=prior_posts_this_week,
        prior_published=prior_published,
    )


def check_char_limits(text: str) -> dict:
    """Check LinkedIn character limits: warn at 1500, reject at 3000."""
    chars = len(text)
    return {
        "ok": chars <= 3000,
        "warning": chars > 1500,
        "chars": chars,
    }


async def generate_post(
    llm: LLMClient,
    theme: str,
    day: str,
    weekday: str,
    settings: dict,
    research_summary: str,
    prior_posts_this_week: list[str],
    prior_published: list[str],
) -> str:
    """Generate a single LinkedIn post via Qwen3-235B."""
    system_prompt = _load_prompt("system_prompt.txt")
    user_prompt = format_post_prompt(
        theme=theme,
        day=day,
        weekday=weekday,
        voice=settings.get("voice", "conversational, expert, first-person"),
        audience=settings.get("audience", "engineering leaders"),
        cta_style=settings.get("cta_style", "soft question"),
        hashtags=settings.get("hashtags", ""),
        research_summary=research_summary,
        prior_posts_this_week="\n---\n".join(prior_posts_this_week) if prior_posts_this_week else "None yet.",
        prior_published="\n---\n".join(prior_published) if prior_published else "None.",
    )

    response = await llm.generate(user_prompt, system_prompt=system_prompt)
    if response.error:
        logger.error("Post generation failed for %s: %s", theme, response.error)
        if response.error == "model_not_supported":
            raise RuntimeError("model_not_supported")
        return ""

    draft = response.text.strip()

    # Strip markdown that LinkedIn doesn't render
    import re
    draft = re.sub(r'\*\*(.+?)\*\*', r'\1', draft)  # **bold** → bold
    draft = re.sub(r'\*(.+?)\*', r'\1', draft)       # *italic* → italic
    draft = re.sub(r'#{1,6}\s*', '', draft)           # ### heading → heading
    draft = re.sub(r'`(.+?)`', r'\1', draft)          # `code` → code
    draft = re.sub(r'- ', '→ ', draft)                # - bullet → → bullet

    limits = check_char_limits(draft)
    if not limits["ok"]:
        logger.warning("Post for %s exceeds 3000 chars (%d). Truncating.", theme, limits["chars"])
        draft = draft[:3000]
    elif limits["warning"]:
        logger.warning("Post for %s is long: %d chars", theme, limits["chars"])

    return draft


async def generate_carousel_content(
    llm: LLMClient,
    theme: str,
    day: str,
    weekday: str,
    research_summary: str,
) -> dict | None:
    """Generate carousel content (hook, points, CTA) via LLM. Returns parsed dict or None."""
    system_prompt = _load_prompt("system_prompt.txt")
    template = _load_prompt("carousel_prompt.txt")
    user_prompt = template.format(
        theme=theme,
        day=day,
        weekday=weekday,
        research_summary=research_summary,
    )

    response = await llm.generate(user_prompt, system_prompt=system_prompt, max_tokens=2000)
    if response.error:
        logger.error("Carousel generation failed for %s: %s", theme, response.error)
        if response.error == "model_not_supported":
            raise RuntimeError("model_not_supported")
        return None

    import json
    text = response.text.strip()
    # Strip markdown code fences if present
    if text.startswith("```"):
        text = text.split("\n", 1)[1] if "\n" in text else text[3:]
        if text.endswith("```"):
            text = text[:-3]
        text = text.strip()

    try:
        data = json.loads(text)
        if "hook" in data and "points" in data:
            logger.info("Carousel content generated: %d points", len(data["points"]))
            return data
        logger.error("Carousel JSON missing required keys")
        return None
    except json.JSONDecodeError as e:
        logger.error("Carousel JSON parse error: %s", e)
        logger.error("Raw LLM output: %s", text[:500])
        return None


async def extract_infographic_data(
    llm: LLMClient,
    post_text: str,
    theme: str,
) -> dict | None:
    """Extract structured infographic data from a generated post."""
    template = _load_prompt("infographic_prompt.txt")
    user_prompt = template.format(post_text=post_text, theme=theme)

    response = await llm.generate(user_prompt, temperature=0.3, max_tokens=2000)
    if response.error:
        logger.error("Infographic extraction failed: %s", response.error)
        return None

    import json
    text = response.text.strip()
    # Strip markdown code fences if present
    if text.startswith("```"):
        text = text.split("\n", 1)[1] if "\n" in text else text[3:]
        if text.endswith("```"):
            text = text[:-3]
        text = text.strip()

    try:
        data = json.loads(text)
        if "title" in data and "points" in data:
            logger.info("Infographic data extracted: %d points", len(data["points"]))
            return data
        logger.error("Infographic JSON missing required keys (title, points)")
        return None
    except json.JSONDecodeError as e:
        logger.error("Infographic JSON parse error: %s", e)
        logger.error("Raw LLM output: %s", text[:500])
        return None


async def check_similarity(llm: LLMClient, draft: str, prior_posts: list[str]) -> bool:
    """Use Qwen to check if draft is >70% semantically similar to any prior post."""
    if not prior_posts:
        return False

    prior_text = "\n---\n".join(prior_posts[:5])
    prompt = f"""Compare this draft LinkedIn post against the prior posts below.
Is the draft >70% semantically similar (same core topic AND similar opening hook) to ANY prior post?
Reply with ONLY "SIMILAR" or "UNIQUE".

DRAFT:
{draft}

PRIOR POSTS:
{prior_text}"""

    response = await llm.generate(prompt, temperature=0.1, max_tokens=50)
    result = response.text.strip().upper()
    is_similar = "SIMILAR" in result
    if is_similar:
        logger.info("Draft flagged as similar to prior post — will regenerate")
    return is_similar
