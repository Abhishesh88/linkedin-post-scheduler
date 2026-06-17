"""Discover trending LinkedIn posts to comment on via You.com search."""

from __future__ import annotations

import json
import logging
import os
import random
import re
from datetime import datetime
from pathlib import Path

logger = logging.getLogger(__name__)

MODULE_DIR = Path(__file__).parent
CONFIG_PATH = MODULE_DIR / "config.json"
STATE_PATH = MODULE_DIR / "state.json"

# Query templates — {topic} and {year} are filled dynamically
_QUERY_TEMPLATES = [
    'site:linkedin.com "{topic}" engineer',
    'site:linkedin.com "{topic}" developer {year}',
    'site:linkedin.com "{topic}" shipped this week',
    'site:linkedin.com "{topic}" trending',
]

# Rotating topic pools — shuffled each run for variety
_TOPIC_POOLS = [
    ["Claude Code", "Cursor AI", "Copilot", "Windsurf", "Kimi K2", "Codex"],
    ["AI agents", "coding agents", "agentic workflows", "MCP servers", "tool use"],
    ["LLM", "GPT-5", "Claude Opus", "Gemini", "DeepSeek", "Qwen"],
    ["RAG", "vector database", "fine-tuning", "embeddings", "prompt engineering"],
    ["system design", "AI infrastructure", "ML ops", "AI architecture"],
    ["engineering productivity", "developer tools", "AI automation", "code review AI"],
    ["engineering manager", "tech lead", "staff engineer", "VP engineering"],
    ["open source AI", "Hugging Face", "Ollama", "local LLM", "self-hosted AI"],
]


def _build_search_queries() -> list[str]:
    """Build dynamic search queries by sampling from topic pools."""
    year = datetime.now().year
    queries = []

    # Shuffle pools and pick topics
    pools = list(_TOPIC_POOLS)
    random.shuffle(pools)

    for pool in pools[:6]:
        topic = random.choice(pool)
        template = random.choice(_QUERY_TEMPLATES)
        queries.append(template.format(topic=topic, year=year))

    # Always include a broad trending query
    queries.append(f'site:linkedin.com AI tools trending {year}')
    queries.append(f'site:linkedin.com "AI" engineering this week {year}')

    return queries


def load_config() -> dict:
    return json.loads(CONFIG_PATH.read_text())


def load_state() -> dict:
    if STATE_PATH.exists():
        return json.loads(STATE_PATH.read_text())
    return {"commented_urls": [], "daily_count": 0, "last_reset": "", "start_date": datetime.now().isoformat()[:10]}


def save_state(state: dict):
    STATE_PATH.write_text(json.dumps(state, indent=2))


def _get_commented_urls() -> set[str]:
    """Get URLs already commented on from CommentQueue Google Sheet."""
    try:
        from src.sheets_client import SheetsClient
        sheets = SheetsClient()
        ws = sheets._spreadsheet.worksheet("CommentQueue")
        rows = ws.get_all_values()
        urls = set()
        for row in rows[1:]:
            if row and row[0]:
                # Store just the activity ID for matching
                match = re.search(r'activity:(\d+)', row[0])
                if match:
                    urls.add(match.group(1))
                urls.add(row[0].strip())
        logger.info("Loaded %d already-commented URLs from CommentQueue", len(urls))
        return urls
    except Exception as e:
        logger.warning("Could not load CommentQueue: %s", e)
        return set()


def _extract_linkedin_posts(search_results: list) -> list[dict]:
    """Extract LinkedIn post URLs and info from search results."""
    posts = []
    seen_ids = set()

    for result in search_results:
        url = result.get("url", "")
        title = result.get("title", "")
        description = result.get("description", "")
        snippets = result.get("snippets", [])

        # Must be a LinkedIn post/activity URL
        if not url or "linkedin.com" not in url:
            continue

        # Extract activity ID from various URL formats
        activity_match = re.search(r'activity[:\-_](\d+)', url)
        post_match = re.search(r'/posts/([^/?]+)', url)
        pulse_match = re.search(r'/pulse/([^/?]+)', url)

        if not activity_match and not post_match and not pulse_match:
            continue

        # Skip pulse/article URLs (can't comment via API)
        if pulse_match and not activity_match:
            continue

        # Deduplicate by activity ID
        post_id = activity_match.group(1) if activity_match else post_match.group(1)
        if post_id in seen_ids:
            continue
        seen_ids.add(post_id)

        # Build proper URL
        if activity_match:
            clean_url = f"https://www.linkedin.com/feed/update/urn:li:activity:{activity_match.group(1)}/"
        else:
            clean_url = url.split("?")[0]

        # Extract author from title (LinkedIn titles are usually "Author on LinkedIn: post text")
        author = ""
        if " on LinkedIn" in title:
            author = title.split(" on LinkedIn")[0].strip()
        elif " | LinkedIn" in title:
            author = title.split(" | LinkedIn")[0].strip()

        # Get post text — prefer snippets, then description, then title
        text_parts = []
        if snippets:
            text_parts.extend(snippets)
        if description:
            text_parts.append(description)
        if title:
            text_parts.append(title)
        text = " ".join(text_parts).strip()

        if text and len(text) > 30:
            posts.append({
                "url": clean_url,
                "text": text[:1000],
                "author": author or "Unknown",
                "post_id": post_id,
            })

    return posts


async def scan_all_targets() -> list[dict]:
    """Discover trending LinkedIn posts via You.com search."""
    from src.search_client import YouSearchClient

    config = load_config()
    state = load_state()

    # Reset daily count
    today = datetime.now().isoformat()[:10]
    if state.get("last_reset") != today:
        state["daily_count"] = 0
        state["last_reset"] = today

    # Check daily limit
    days_since_start = (datetime.now() - datetime.fromisoformat(state.get("start_date", today))).days
    limit = config["daily_limit"] if days_since_start > config.get("warmup_days", 14) else config.get("warmup_limit", 5)

    if state["daily_count"] >= limit:
        logger.info("Daily limit reached (%d/%d)", state["daily_count"], limit)
        return []

    # Get already-commented URLs
    commented = _get_commented_urls()

    # Search for trending LinkedIn posts with dynamic queries
    search = YouSearchClient()
    all_posts = []
    seen_authors = set()
    queries = _build_search_queries()

    try:
        for query in queries:
            logger.info("Searching: %s", query[:60])
            responses = await search.batch_search([query])

            for resp in responses:
                results = [{"url": r.url, "title": r.title, "description": r.description, "snippets": r.snippets} for r in resp.web_results]
                posts = _extract_linkedin_posts(results)

                for post in posts:
                    # Skip already commented
                    if post["post_id"] in commented or post["url"] in commented:
                        continue
                    # 1 post per author
                    if post["author"] in seen_authors:
                        continue

                    seen_authors.add(post["author"])
                    all_posts.append(post)
    finally:
        await search.close()

    save_state(state)

    remaining = limit - state["daily_count"]
    logger.info("Discovered %d new posts from %d unique authors", len(all_posts), len(seen_authors))
    return all_posts[:remaining]
