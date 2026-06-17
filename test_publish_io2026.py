#!/usr/bin/env python3
"""Generate + publish Google I/O 2026 infographic post to LinkedIn."""
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

logger = setup_logging("publish_io2026")

POST_TEXT = """Google I/O 2026 just killed 5 tools I used every day.

Not exaggerating. In one keynote, Google shipped replacements for tools I've paid for and relied on for years.

Here's what changed:

1. Gemini Spark replaced my personal assistant stack

Gemini Spark is a 24/7 AI agent that drafts emails, manages RSVPs, creates docs, and syncs across every device. It compiles info across apps automatically.

I was paying for Notion AI + Zapier + a calendar assistant. All three just became redundant.

2. Agentic AI Search replaced my research workflow

Google Search isn't a search engine anymore. It's an AI agent that DOES things for you. It doesn't just find answers. It takes action.

I used to search, read 5 tabs, copy-paste, and synthesize. Now Search does the synthesis and hands me the result.

3. AI Mode replaced ChatGPT for quick questions

The new AI Mode in Google Search is basically ChatGPT built into every browser. No separate tab. No login. No subscription.

For 80% of my daily AI questions, I no longer open Claude or ChatGPT. I just search.

4. The new Search Box replaced 3 Chrome extensions

Google rebuilt the Search box from scratch for the first time in 25 years. It's now an intelligent command center.

Autocomplete, context-aware suggestions, and inline answers. My tab manager, quick-answer extension, and bookmark search tool are all gone.

5. Gemini 3.5 replaced my secondary LLM

The new Gemini 3.5 family handles tasks that used to require switching between models. Multi-language fluency, long-context reasoning, and code generation in one model.

I used to keep 3 LLM subscriptions. Now I need 2.

The pattern is clear:

Google isn't building features. It's building replacements.

Every tool that sits between you and information is at risk. Every SaaS that charges you to organize, search, or summarize is on the clock.

The question isn't "Will AI replace my tools?"

It's "Which tools survive the next 12 months?"

What tool did Google I/O just make redundant for you?

#GoogleIO2026 #AI #Gemini #ArtificialIntelligence #ProductivityTools"""

INFOGRAPHIC_DATA = {
    "title": "GOOGLE I/O 2026 JUST KILLED 5 TOOLS I USED EVERY DAY",
    "highlight_word": "KILLED 5 TOOLS",
    "category": "GOOGLE I/O 2026",
    "subtitle": "One keynote. Five tools replaced.",
    "accent": "red",
    "stats": [
        {"number": "100+", "label": "AI Features\nAnnounced"},
        {"number": "5", "label": "Tools\nReplaced"},
        {"number": "25yr", "label": "First Search\nRedesign"},
        {"number": "24/7", "label": "AI Agent\nAlways On"},
    ],
    "points": [
        {"title": "GEMINI SPARK REPLACES ASSISTANTS",
         "body": "24/7 AI agent: drafts emails, manages RSVPs, creates docs, syncs across all devices. Notion AI + Zapier + calendar assistant gone."},
        {"title": "AGENTIC SEARCH DOES THE WORK",
         "body": "Google Search isn't a search engine anymore. It's an AI agent that takes action for you. No more 5-tab research sessions."},
        {"title": "AI MODE REPLACES CHATGPT",
         "body": "ChatGPT built into every browser. No separate tab, no login, no subscription. 80% of daily AI questions handled."},
        {"title": "NEW SEARCH BOX = COMMAND CENTER",
         "body": "First redesign in 25 years. Intelligent autocomplete, context-aware suggestions, inline answers. 3 Chrome extensions deleted."},
        {"title": "GEMINI 3.5 REPLACES SECONDARY LLMS",
         "body": "Multi-language fluency, long-context reasoning, code generation. One model handles what took 3 subscriptions before."},
    ],
}


async def run(dry_run: bool = False):
    logger.info("Generating Google I/O 2026 infographic...")
    image_path = generate_infographic(
        title=INFOGRAPHIC_DATA["title"],
        points=INFOGRAPHIC_DATA["points"],
        category=INFOGRAPHIC_DATA["category"],
        subtitle=INFOGRAPHIC_DATA["subtitle"],
        highlight_word=INFOGRAPHIC_DATA["highlight_word"],
        accent=INFOGRAPHIC_DATA["accent"],
        stats=INFOGRAPHIC_DATA["stats"],
        branding_text="Follow for AI updates",
        filename="google-io-2026-post.png",
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
            f"Published Google I/O 2026 post!\nPost ID: {result['post_id']}"
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
