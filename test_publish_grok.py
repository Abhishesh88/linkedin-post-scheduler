#!/usr/bin/env python3
"""Generate + publish Grok Build post to LinkedIn with infographic."""
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

logger = setup_logging("publish_grok")

POST_TEXT = """xAI just launched Grok Build beta.

A terminal-native AI coding agent with image generation, video, and CLI automations.

One curl command to install. And it's coming for Claude Code.

Here's what makes it different:

1. Plan Mode before every change

Grok Build doesn't blindly write code. It generates a structured plan first: files to modify, new files to create, step-by-step execution.

You review. Edit. Reorder. Reject steps. Then it executes.

This is what most coding agents get wrong. They act first, ask later. Grok plans first.

2. Parallel Subagents

Multiple AI processes handle tasks simultaneously. One scans dependencies while another writes code. A third runs tests.

The result? Multi-file refactors that used to take 20 minutes now take 3.

3. Arena Mode

It edits your files, then presents alternative implementations for you to choose from. Variable autonomy. You pick the level of control.

4. MCP Support built in

Connects to databases, CI/CD pipelines, and external tools via Model Context Protocol. This is what turns a coding assistant into a coding system.

5. Image + video generation from terminal

Not just code. Grok Build can generate images and video assets directly from your terminal. No browser. No separate tool.

For developers building apps that need media, this is massive.

The catch?

SuperGrok plan: $300/month for full access (Arena Mode + MCP).
Free tier: 50 daily requests, no Arena Mode.

The AI coding agent wars just got a new contender.

Claude Code vs Grok Build vs Codex CLI vs Cursor.

2026 is the year every developer gets a choice.

Which AI coding agent are you using?

#GrokBuild #xAI #ClaudeCode #AICoding #DeveloperTools"""

INFOGRAPHIC_DATA = {
    "title": "xAI LAUNCHES GROK BUILD: A NEW AI CODING AGENT",
    "highlight_word": "GROK BUILD",
    "category": "BREAKING LAUNCH",
    "subtitle": "Terminal-native. Plan-first. Multi-agent.",
    "accent": "purple",
    "stats": [
        {"number": "1", "label": "Curl Command\nTo Install"},
        {"number": "50", "label": "Free Daily\nRequests"},
        {"number": "$300", "label": "Full Access\nPer Month"},
        {"number": "3x", "label": "Faster Multi-\nFile Refactors"},
    ],
    "points": [
        {"title": "PLAN MODE BEFORE EVERY CHANGE",
         "body": "Generates structured plan: files to modify, steps to execute. You review, edit, reorder before it touches code."},
        {"title": "PARALLEL SUBAGENTS",
         "body": "Multiple AI processes run simultaneously. One scans deps, another writes code, a third runs tests. 20-min refactors in 3 min."},
        {"title": "ARENA MODE",
         "body": "Edits files, then shows alternative implementations. You pick the best. Variable autonomy — choose your level of control."},
        {"title": "MCP SUPPORT BUILT IN",
         "body": "Connects to databases, CI/CD, external tools via Model Context Protocol. Turns a coding assistant into a coding system."},
        {"title": "IMAGE + VIDEO FROM TERMINAL",
         "body": "Generate images and video assets directly from CLI. No browser, no separate tool. Build apps with media, all from terminal."},
        {"title": "CLAUDE CODE COMPETITOR",
         "body": "Excels at multi-file refactoring and parallel execution. Claude Code still leads in conversational debugging. The AI coding wars heat up."},
    ],
}


async def run(dry_run: bool = False):
    logger.info("Generating Grok Build infographic...")
    image_path = generate_infographic(
        title=INFOGRAPHIC_DATA["title"],
        points=INFOGRAPHIC_DATA["points"],
        category=INFOGRAPHIC_DATA["category"],
        subtitle=INFOGRAPHIC_DATA["subtitle"],
        highlight_word=INFOGRAPHIC_DATA["highlight_word"],
        accent=INFOGRAPHIC_DATA["accent"],
        stats=INFOGRAPHIC_DATA["stats"],
        branding_text="Follow for AI updates",
        filename="grok-build-post.png",
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
            f"Published Grok Build post!\nPost ID: {result['post_id']}"
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
