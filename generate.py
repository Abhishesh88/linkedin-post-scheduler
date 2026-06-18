#!/usr/bin/env python3
"""Daily post generation: research → generate → image → sheets → telegram.

Generates ONE post per day (not a weekly batch).
Runs daily via GitHub Actions at 06:00 UTC on weekdays.

Usage:
  python generate.py              # Generate today's post
  python generate.py --dry-run    # Preview without generating
"""
from __future__ import annotations

import argparse
import asyncio
import logging
from datetime import date

from src.utils import setup_logging
from src.search_client import YouSearchClient
from src.llm_client import LLMClient
from src.researcher import research_theme, build_research_summary, discover_trending_topic
from src.post_generator import generate_post, generate_carousel_content, check_similarity, extract_infographic_data
from src.sheets_client import SheetsClient
from src.image_generator import generate_image
from src.carousel_generator import generate_carousel_pdf
from src.video_finder import find_video_for_theme
from src.diagram_finder import find_diagram_image
from src import telegram_bot

logger = setup_logging("generate")


async def run_generate(dry_run: bool = False, force: bool = False, override_theme: str = "", force_video: bool = False, max_retries: int = 3, retry_delay_sec: int = 30):
    """Generate one post for today.

    Fail-fast retry: tries up to max_retries with a short retry_delay_sec gap if the
    model is unavailable, then exits cleanly. We do NOT sleep for long periods inside
    the job (that burns scheduler/runner minutes). The 'today already posted' check at
    the top makes it safe for the scheduler to simply re-trigger later.
    """
    today = date.today()
    weekday = today.strftime("%A")

    # Weekend skip removed — posts every day

    logger.info("=== Generating post for %s (%s) ===", today.isoformat(), weekday)

    sheets = SheetsClient()
    search = YouSearchClient()
    llm = LLMClient()

    try:
        # 1. Read settings
        settings = sheets.get_settings()

        # 2. Check if today already has a pending/approved post sent to Telegram (skip if force)
        if not force:
            existing = sheets.get_posts_by_status("pending_approval") + sheets.get_posts_by_status("approved")
            todays_existing = [p for p in existing if p.get("day") == today.isoformat()]
            todays_sent = [p for p in todays_existing if p.get("telegram_msg_id", "").strip()]
            if todays_sent:
                logger.info("Today already has a pending/approved post sent to Telegram (row %s, theme: %s). Skipping.",
                            todays_sent[0].get("_row", "?"), todays_sent[0].get("theme", "?"))
                return
            if todays_existing and not todays_sent:
                logger.warning("Found %d stale post(s) for today without Telegram msg — ignoring and regenerating.",
                               len(todays_existing))

        # 3. Discover trending topic dynamically (or use override)
        prior_posts = sheets.get_prior_posts(limit=10)
        recent_themes = [p.get("theme", "") for p in prior_posts]
        if override_theme:
            theme = override_theme
            category = "ai tools"
            logger.info("Using override theme: %s", theme)
        else:
            logger.info("Discovering what's trending right now...")
            theme, category = await discover_trending_topic(search, llm, recent_themes)

        logger.info("Theme: %s [%s]", theme, category)

        if dry_run:
            logger.info("[DRY RUN] Would generate post for: %s", theme)
            return

        # 4. Research
        logger.info("Researching...")
        data = await research_theme(theme, search, category=category)
        summary = build_research_summary(data)
        logger.info("Research: %d sources, %d snippets", data["total_sources"], data["total_snippets"])

        # 5. Generate post (with retry — model may be temporarily unavailable)
        prior_texts = [p.get("draft_text", "") for p in prior_posts if p.get("draft_text")]
        draft = ""
        for attempt in range(1, max_retries + 1):
            logger.info("Generating post via Qwen3-235B (attempt %d/%d)...", attempt, max_retries)
            try:
                draft = await generate_post(
                    llm=llm,
                    theme=theme,
                    day=today.isoformat(),
                    weekday=weekday,
                    settings=settings,
                    research_summary=summary,
                    prior_posts_this_week=[],
                    prior_published=prior_texts,
                )
            except RuntimeError as e:
                if "model_not_supported" in str(e):
                    logger.error("Model not supported — aborting (no point retrying). Update HF_MODEL secret.")
                    await telegram_bot.send_notification(
                        f"FATAL: Model not supported by HuggingFace providers. "
                        f"Update HF_MODEL secret. Theme was: {theme}"
                    )
                    return
                raise
            if draft:
                break
            if attempt < max_retries:
                logger.warning("Model unavailable, retrying in %d seconds (attempt %d/%d)", retry_delay_sec, attempt, max_retries)
                await asyncio.sleep(retry_delay_sec)
            else:
                logger.error("Post generation failed after %d attempts — exiting; scheduler will re-trigger.", max_retries)
                await telegram_bot.send_notification(f"ERROR: Model unavailable for: {theme} after {max_retries} attempts. Will retry on next scheduled run.")
                return

        # Dedup check
        is_similar = await check_similarity(llm, draft, prior_texts)
        if is_similar:
            logger.info("Duplicate detected, regenerating...")
            draft = await generate_post(
                llm=llm,
                theme=theme,
                day=today.isoformat(),
                weekday=weekday,
                settings=settings,
                research_summary=summary + "\n\nIMPORTANT: Take a COMPLETELY different angle.",
                prior_posts_this_week=[],
                prior_published=prior_texts,
            )

        if not draft:
            return

        char_count = len(draft)
        logger.info("Generated: %d chars", char_count)

        # 6. Alternate video and image posts based on day of month (odd=video, even=image)
        carousel_path = None
        carousel_data = None
        video = None
        image_path = None

        import json as _json

        is_video_day = force_video or today.day % 2 == 1  # odd days = video, even days = image, or --video flag
        logger.info("Day %d — %s post%s", today.day, "VIDEO" if is_video_day else "IMAGE", " (forced)" if force_video else "")

        if is_video_day:
            # VIDEO POST — search for short YouTube clip
            logger.info("Searching for short demo video...")
            video = await find_video_for_theme(theme, search)
            if video:
                logger.info("Found video: %s — %s", video["title"][:50], video["url"][:80])
            else:
                logger.info("No video found, falling back to infographic image")
                is_video_day = False

        if not is_video_day:
            # INFOGRAPHIC IMAGE — extract points from post, render via Playwright
            logger.info("Extracting infographic data from post...")
            infographic_data = await extract_infographic_data(llm, draft, theme)

            if infographic_data and infographic_data.get("points"):
                logger.info("Generating infographic image (%d points)...", len(infographic_data["points"]))
                image_path = await generate_image(
                    theme=infographic_data.get("title", theme),
                    category=infographic_data.get("category", category),
                    points=infographic_data["points"],
                    highlight_word=infographic_data.get("highlight_word", ""),
                    accent=infographic_data.get("accent", "teal"),
                    subtitle=infographic_data.get("subtitle", ""),
                    stats=infographic_data.get("stats"),
                    branding_text="Follow for more",
                )
                if image_path:
                    logger.info("Infographic generated: %s", image_path)
            else:
                logger.info("Infographic extraction failed, falling back to diagram search")
                image_path = await find_diagram_image(theme, search)

            if not image_path:
                logger.info("No image yet, using branded fallback")
                image_path = await generate_image(theme, category=category)

        # 7. Write to Google Sheets
        logger.info("Writing to Sheets...")
        if carousel_data:
            research_field = _json.dumps({"carousel": carousel_data})
        elif video and video.get("url"):
            research_field = _json.dumps({"video_url": video["url"], "video_title": video.get("title", "")})
        else:
            research_field = summary[:500]
        post_data = {
            "week_start": today.isoformat(),
            "day": today.isoformat(),
            "theme": theme,
            "draft_text": draft,
            "char_count": char_count,
            "research_summary": research_field,
            "status": "pending_approval",
            "suggested_time": "09:00 UTC",
        }
        sheets.append_post(post_data)
        posts_ws = sheets._ws("Posts")
        row_count = len(posts_ws.get_all_values())

        # 8. Send to Telegram with approve/reject buttons
        post_type = "VIDEO" if (video and video.get("url")) else ("CAROUSEL" if carousel_path else "IMAGE")
        logger.info("Sending %s post to Telegram...", post_type)

        if carousel_path:
            await telegram_bot.send_document(carousel_path, caption=f"Carousel: {theme}")

        msg_id = await telegram_bot.send_draft(
            day=today.isoformat(),
            weekday=weekday,
            theme=f"[{post_type}] {theme}",
            draft_text=draft,
            char_count=char_count,
            suggested_time="09:00 UTC",
            row_number=row_count,
            image_path=image_path,
        )
        if msg_id:
            sheets.update_post_status(row_count, "pending_approval", telegram_msg_id=msg_id)

        if video and video.get("url"):
            await telegram_bot.send_notification(
                f"VIDEO will auto-download + upload on approve:\n{video['title']}\n{video['url']}"
            )

        logger.info("=== Done! Post pending approval (row %d) ===", row_count)

    finally:
        await search.close()
        await llm.close()


def main():
    parser = argparse.ArgumentParser(description="Generate today's LinkedIn post")
    parser.add_argument("--dry-run", action="store_true", help="Preview without generating")
    parser.add_argument("--force", action="store_true", help="Force generation even on weekends")
    parser.add_argument("--theme", type=str, default="", help="Override theme with a specific trending topic")
    parser.add_argument("--video", action="store_true", help="Force video post regardless of day")
    args = parser.parse_args()

    asyncio.run(run_generate(dry_run=args.dry_run, force=args.force, override_theme=args.theme, force_video=args.video))


if __name__ == "__main__":
    main()
