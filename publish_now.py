#!/usr/bin/env python3
"""Direct LinkedIn publisher v2 — optimized discovery engine.

Multi-source discovery (GitHub API + You.com) → star velocity scoring →
spam filtering → media detection → post generation → LinkedIn publish.

Usage:
  python publish_now.py                  # Auto-discover + publish
  python publish_now.py --theme "owner/repo: description"
  python publish_now.py --dry-run        # Preview without publishing
  python publish_now.py --discover-only  # Just show what it would pick
"""
from __future__ import annotations

import argparse
import asyncio
import json
import logging
from datetime import date

from dotenv import load_dotenv
load_dotenv()

from src.utils import setup_logging
from src.search_client import YouSearchClient
from src.llm_client import LLMClient
from src.researcher import research_theme, build_research_summary
from src.post_generator import generate_post
from src.sheets_client import SheetsClient
from src.linkedin_publisher import publish_post
from src.discovery import discover_trending_repo, pick_best_with_media, check_repo_media, download_media
from src import telegram_bot

logger = setup_logging("publish_now")

# Post type rotation based on day of week
POST_TYPES = {
    0: "repo",        # Monday — trending repo
    1: "comparison",  # Tuesday — X vs Y
    2: "concept",     # Wednesday — architecture breakdown
    3: "repo",        # Thursday — trending repo
    4: "benchmark",   # Friday — benchmark/results
    5: "repo",        # Saturday — trending repo
    6: "repo",        # Sunday — trending repo
}


async def run(dry_run: bool = False, discover_only: bool = False, override_theme: str = ""):
    today = date.today()
    weekday = today.strftime("%A")
    post_type = POST_TYPES.get(today.weekday(), "repo")

    logger.info("=== publish_now v2 — %s (%s) — type: %s ===", today.isoformat(), weekday, post_type)

    sheets = SheetsClient()
    search = YouSearchClient()
    llm = LLMClient()

    try:
        prior_posts = sheets.get_prior_posts(limit=15)
        recent_themes = [p.get("theme", "") for p in prior_posts]

        # 1. DISCOVER
        if override_theme:
            # Manual theme — check for media
            import re
            repo_match = re.search(r'([a-zA-Z0-9_.-]+/[a-zA-Z0-9_.-]+)', override_theme)
            media_path = None
            if repo_match:
                media_info = check_repo_media(repo_match.group(1))
                if media_info:
                    media_path = download_media(media_info, repo_match.group(1))
            candidate = {"name": override_theme.split(":")[0].strip(), "desc": override_theme, "stars": 0}
            theme = override_theme
        else:
            logger.info("Discovering trending AI repos...")
            candidates = await discover_trending_repo(search, recent_themes)

            if discover_only:
                logger.info("\n=== TOP 10 CANDIDATES ===")
                for i, c in enumerate(candidates[:10], 1):
                    media_tag = f"[{c['media_info']['type']}]" if c.get("media_info") else "[no media]"
                    logger.info("%2d. %s | %d stars | %.0f/day | score=%.0f | %s | %s",
                                i, c["name"], c["stars"], c["velocity"], c["score"],
                                media_tag, c["desc"][:50])
                return

            if not candidates:
                logger.error("No candidates found")
                return

            candidate, media_path = pick_best_with_media(candidates)
            if not candidate:
                logger.error("No suitable repo found")
                return

            theme = f"{candidate['name']} ({candidate.get('stars', 0)} stars): {candidate.get('desc', '')}"

        logger.info("Theme: %s", theme)
        logger.info("Media: %s", media_path or "none")

        if dry_run:
            logger.info("[DRY RUN] Would generate and publish: %s", theme[:80])
            return

        # 2. RESEARCH
        logger.info("Researching...")
        data = await research_theme(theme, search, category="ai tools")
        summary = build_research_summary(data)
        logger.info("Research: %d sources, %d snippets", data["total_sources"], data["total_snippets"])

        # 3. GENERATE POST
        settings = sheets.get_settings()
        prior_texts = [p.get("draft_text", "") for p in prior_posts if p.get("draft_text")]
        draft = await generate_post(
            llm=llm, theme=theme, day=today.isoformat(), weekday=weekday,
            settings=settings, research_summary=summary,
            prior_posts_this_week=[], prior_published=prior_texts,
        )
        if not draft:
            logger.error("Post generation failed")
            return

        logger.info("Generated: %d chars", len(draft))

        # 4. PUBLISH
        video_path = media_path if media_path and media_path.endswith(".mp4") else None
        image_path = media_path if media_path and not media_path.endswith(".mp4") else None

        logger.info("Publishing to LinkedIn (%s)...", "video" if video_path else "image" if image_path else "text")
        result = await publish_post(text=draft, image_path=image_path, video_path=video_path)

        if result["success"]:
            logger.info("PUBLISHED: %s", result["post_id"])
            sheets.append_post({
                "week_start": today.isoformat(),
                "day": today.isoformat(),
                "theme": theme,
                "draft_text": draft,
                "char_count": len(draft),
                "research_summary": summary[:500],
                "status": "published",
                "suggested_time": "now",
            })
            await telegram_bot.send_notification(
                f"Published to LinkedIn:\n{theme[:100]}\n\nPost ID: {result['post_id']}"
            )
        else:
            logger.error("Publish failed: %s", result["error"])
            await telegram_bot.send_notification(f"LinkedIn publish FAILED: {result['error']}")

    finally:
        await search.close()
        await llm.close()


def main():
    parser = argparse.ArgumentParser(description="Publish trending AI post to LinkedIn")
    parser.add_argument("--dry-run", action="store_true", help="Preview without publishing")
    parser.add_argument("--discover-only", action="store_true", help="Only show discovery results")
    parser.add_argument("--theme", type=str, default="", help="Override theme")
    args = parser.parse_args()

    asyncio.run(run(dry_run=args.dry_run, discover_only=args.discover_only, override_theme=args.theme))


if __name__ == "__main__":
    main()
