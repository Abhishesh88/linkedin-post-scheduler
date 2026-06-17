#!/usr/bin/env python3
"""Test: Generate infographic + publish to LinkedIn directly.

Skips LLM (uses hardcoded post) to test the infographic → LinkedIn pipeline.

Usage:
  python3 test_publish_infographic.py              # Generate + publish
  python3 test_publish_infographic.py --dry-run     # Generate only, don't publish
"""
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

logger = setup_logging("test_publish")

# Pre-written post text (the teal "5 tricks" post — user's favorite)
POST_TEXT = """5 Claude Code tricks that saved me 20+ hours this week.

I tracked my time. Claude Code saved me 23 hours. Not in theory. In actual work I didn't have to do manually.

Here are the 5 tricks:

1. "Read the entire codebase first" prompt

Before any task, I type: "Explore the codebase. Understand the architecture. Then tell me what you found."

Takes 60 seconds. Saves hours of wrong assumptions.

2. One-shot test generation

I point Claude Code at any file and say: "Write comprehensive tests. Cover edge cases. Run them."

It writes the tests. Runs them. Fixes failures. Until green.

Monday: 0% coverage to 87% coverage in 45 minutes.

3. The "refactor chain"

Instead of refactoring one file, I say: "Refactor this module. Update every file that imports from it. Run all tests."

It traces the dependency graph. Updates 15 files. Zero broken imports.

4. Git commit messages on autopilot

After any change: "Commit with a descriptive message following conventional commits."

My git log went from "fix stuff" to structured, searchable history.

5. Debug with context, not screenshots

Old: Copy error, paste in ChatGPT, get generic answer, still stuck.

New: "This test is failing. Read the test, read the source, figure out why, fix it."

Claude Code reads both files, understands the mismatch, fixes it.

Wednesday: A bug that had 3 of us stuck for 2 hours. Claude Code fixed it in 4 minutes.

The 23-hour breakdown:
Test writing: 8 hrs saved
Refactoring: 6 hrs saved
Debugging: 5 hrs saved
Boilerplate/config: 4 hrs saved

That's 3 full working days. Every single week.

Stop copy-pasting into chat windows. Start building with Claude Code in your terminal.

#ClaudeCode #DeveloperProductivity #AI #CodingTips #Anthropic"""

# Infographic data (pre-extracted, matching the post)
INFOGRAPHIC_DATA = {
    "title": "5 CLAUDE CODE TRICKS THAT SAVED ME 20+ HOURS THIS WEEK",
    "highlight_word": "20+ HOURS",
    "category": "PRODUCTIVITY TIPS",
    "subtitle": "Tested and measured results",
    "accent": "teal",
    "stats": [
        {"number": "23h", "label": "Saved\nPer Week"},
        {"number": "87%", "label": "Test Coverage\nin 45 Min"},
        {"number": "15", "label": "Files Auto\nRefactored"},
        {"number": "4m", "label": "Bug Fix vs\n2 Hours"},
    ],
    "points": [
        {"title": "READ CODEBASE FIRST",
         "body": "Before any task: 'Explore the codebase. Understand the architecture.' Takes 60 seconds. Saves hours of wrong assumptions."},
        {"title": "ONE-SHOT TEST GENERATION",
         "body": "Point at any file: 'Write comprehensive tests. Cover edge cases. Run them.' Monday: 0% to 87% coverage in 45 minutes."},
        {"title": "THE REFACTOR CHAIN",
         "body": "'Refactor this module. Update every file that imports from it. Run all tests.' 15 files updated. Zero broken imports."},
        {"title": "GIT COMMITS ON AUTOPILOT",
         "body": "After any change: 'Commit with conventional commits format.' Git log went from 'fix stuff' to searchable, structured history."},
        {"title": "DEBUG WITH FULL CONTEXT",
         "body": "'This test is failing. Read test + source, figure out why, fix it.' A 2-hour team bug fixed in 4 minutes."},
    ],
}


async def run(dry_run: bool = False):
    # 1. Generate infographic
    logger.info("Generating infographic image...")
    image_path = generate_infographic(
        title=INFOGRAPHIC_DATA["title"],
        points=INFOGRAPHIC_DATA["points"],
        category=INFOGRAPHIC_DATA["category"],
        subtitle=INFOGRAPHIC_DATA["subtitle"],
        highlight_word=INFOGRAPHIC_DATA["highlight_word"],
        accent=INFOGRAPHIC_DATA["accent"],
        stats=INFOGRAPHIC_DATA["stats"],
        branding_text="Follow for more",
        filename="publish-test-infographic.png",
    )
    logger.info("Infographic: %s", image_path)

    if dry_run:
        logger.info("[DRY RUN] Would publish with image: %s", image_path)
        logger.info("Post text (%d chars):\n%s", len(POST_TEXT), POST_TEXT[:200])
        return

    # 2. Publish to LinkedIn
    logger.info("Publishing to LinkedIn with infographic...")
    result = await publish_post(text=POST_TEXT, image_path=image_path)

    if result["success"]:
        logger.info("PUBLISHED! Post ID: %s", result["post_id"])
        await telegram_bot.send_notification(
            f"Published infographic post to LinkedIn!\nPost ID: {result['post_id']}"
        )
    else:
        logger.error("Publish failed: %s", result["error"])


def main():
    parser = argparse.ArgumentParser(description="Test infographic publish to LinkedIn")
    parser.add_argument("--dry-run", action="store_true", help="Generate image only, don't publish")
    args = parser.parse_args()
    asyncio.run(run(dry_run=args.dry_run))


if __name__ == "__main__":
    main()
