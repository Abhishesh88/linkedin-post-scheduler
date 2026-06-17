#!/usr/bin/env python3
"""Generate + publish Claude Opus 4.8 post with infographic to LinkedIn."""
from __future__ import annotations

import argparse
import asyncio
import logging

from dotenv import load_dotenv
load_dotenv()

from src.utils import setup_logging
from src.image_generator import generate_infographic
from src.linkedin_publisher import publish_post
from src import telegram_bot

logger = setup_logging("publish_opus48")

POST_TEXT = """Anthropic just dropped Claude Opus 4.8.

Same price. Dramatically better. Here's what actually changed:

1. It catches its own mistakes now

Opus 4.8 is 4x less likely to let flawed code pass without flagging it. Early testers say it asks the right questions, catches its own bugs, and pushes back when your plan doesn't make sense.

This is the difference between an AI that agrees with everything and one that actually thinks.

2. Dynamic Workflows (Research Preview)

Claude Code can now spin up hundreds of parallel subagents in a single session. Codebase-scale migrations across hundreds of thousands of lines of code. With test suite validation.

One session. Hundreds of agents. Your entire repo.

3. Effort Control

You can now choose how hard Claude thinks. High effort for deep architecture decisions. Low effort for quick formatting tasks.

This isn't just a speed toggle. It's a rate-limit strategy. Run low effort for bulk tasks and save your quota for the problems that actually need deep reasoning.

4. Mid-task system prompts

You can now inject system instructions mid-conversation without breaking prompt caching or requiring a user turn. For anyone building agents, this is massive. Dynamic behavior changes without restarting the context.

5. New benchmark highs

OSWorld-Verified: 82.3%
First model to break 10% all-pass on Legal Agent Benchmark
Terminal-Bench 2.1 improvements
Finance Agent v2 gains

6. Alignment improvements

Opus 4.8 scores new highs on supporting user autonomy and acting in user's best interest. Misaligned behavior rates are substantially lower than 4.7.

Pricing unchanged:
$5/M input tokens, $25/M output tokens
Fast mode: $10/$50 (3x faster)

API: claude-opus-4-8

The model that catches its own mistakes, runs hundreds of parallel agents, and lets you control how hard it thinks.

Available now.

What's the first thing you'd test with Dynamic Workflows?

#ClaudeOpus #Anthropic #AI #ClaudeCode #DeveloperTools"""

INFOGRAPHIC_DATA = {
    "title": "CLAUDE OPUS 4.8: SAME PRICE, DRAMATICALLY BETTER",
    "highlight_word": "OPUS 4.8",
    "category": "NEW MODEL LAUNCH",
    "subtitle": "Catches its own mistakes. Runs 100s of agents.",
    "accent": "orange",
    "stats": [
        {"number": "4x", "label": "Fewer Bugs\nPass Unnoticed"},
        {"number": "82.3%", "label": "OSWorld\nVerified"},
        {"number": "$5", "label": "Per M Input\nTokens"},
        {"number": "100s", "label": "Parallel\nSubagents"},
    ],
    "points": [
        {"title": "CATCHES ITS OWN MISTAKES",
         "body": "4x less likely to let flawed code pass. Asks the right questions, pushes back when your plan is wrong."},
        {"title": "DYNAMIC WORKFLOWS",
         "body": "Hundreds of parallel subagents in one session. Codebase-scale migrations across 100K+ lines with test validation."},
        {"title": "EFFORT CONTROL",
         "body": "Choose how hard Claude thinks. High for architecture, low for formatting. Save rate limits for real problems."},
        {"title": "MID-TASK SYSTEM PROMPTS",
         "body": "Inject system instructions mid-conversation without breaking caching. Dynamic agent behavior changes on the fly."},
        {"title": "NEW BENCHMARK HIGHS",
         "body": "OSWorld 82.3%. First to break 10% Legal Agent all-pass. Terminal-Bench 2.1 and Finance Agent v2 gains."},
        {"title": "BETTER ALIGNMENT",
         "body": "New highs on user autonomy and best interest scores. Misaligned behavior rates substantially lower than 4.7."},
    ],
}


async def run(dry_run: bool = False):
    logger.info("Generating Claude Opus 4.8 infographic...")
    image_path = generate_infographic(
        title=INFOGRAPHIC_DATA["title"],
        points=INFOGRAPHIC_DATA["points"],
        category=INFOGRAPHIC_DATA["category"],
        subtitle=INFOGRAPHIC_DATA["subtitle"],
        highlight_word=INFOGRAPHIC_DATA["highlight_word"],
        accent=INFOGRAPHIC_DATA["accent"],
        stats=INFOGRAPHIC_DATA["stats"],
        branding_text="Follow for AI updates",
        filename="claude-opus-48-post.png",
    )
    logger.info("Infographic: %s", image_path)

    if dry_run:
        logger.info("[DRY RUN] Would publish with image: %s", image_path)
        logger.info("Post text (%d chars):\n%s", len(POST_TEXT), POST_TEXT[:300])
        return

    logger.info("Publishing to LinkedIn...")
    result = await publish_post(text=POST_TEXT, image_path=image_path)

    if result["success"]:
        logger.info("PUBLISHED! Post ID: %s", result["post_id"])
        await telegram_bot.send_notification(
            f"Published Claude Opus 4.8 post!\nPost ID: {result['post_id']}"
        )
    else:
        logger.error("Publish failed: %s", result["error"])


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    asyncio.run(run(dry_run=args.dry_run))


if __name__ == "__main__":
    main()
