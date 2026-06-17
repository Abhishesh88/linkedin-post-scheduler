#!/usr/bin/env python3
"""Generate + publish Microsoft Build 2026 post with infographic."""
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

logger = setup_logging("publish_msbuild")

POST_TEXT = """Microsoft Build 2026 just shipped the future of developer tools.

Not incremental updates. A full platform shift.

Here's what every engineer needs to know:

1. Microsoft Scout — your always-on personal agent

Not Copilot. Not a chatbot. An always-on agent that works across your entire Microsoft stack autonomously. It plans, executes, and follows up without you asking.

This is what Copilot was supposed to be. Scout is what it became.

2. GitHub Copilot Desktop App

Copilot is no longer just an IDE extension. It's now a standalone desktop app with an agent-native experience. Full project awareness, not just line-by-line autocomplete.

The difference between suggesting code and building features.

3. Project Solara — agent-first computing

Microsoft is redesigning Windows around AI agents. Not adding AI to Windows. Redesigning Windows FOR agents.

This is the biggest signal from Build. The operating system itself is becoming agent-native.

4. 7 new AI models from Mustafa Suleyman

Seven new models launched at once. Enterprise-grade. Plus a Mayo Clinic partnership to build a frontier AI model specifically for healthcare.

Microsoft is not just using AI. They're building domain-specific foundation models.

5. Azure Cobalt 200 VMs

50% performance improvement over previous gen. Fully optimized for agentic AI workloads. If you're running AI agents at scale, your infrastructure just got significantly cheaper.

6. Agent Control Specification

An open standard for portable runtime governance of AI agents. This solves the "how do we control agents in production" problem that every enterprise is hitting right now.

Not another framework. A specification. Portable across any runtime.

The pattern from Build 2026:

Microsoft is not adding AI to existing products.
They're rebuilding every product around agents.

Windows. GitHub. Azure. Office. Search.

Every layer of the stack is going agent-native.

The companies that adapt to agent-first architecture will outperform. The ones still treating AI as a feature will fall behind.

What's the most impactful announcement from Build for your team?

#MicrosoftBuild #AI #GitHubCopilot #Azure #DeveloperTools #AIAgents"""

INFOGRAPHIC_DATA = {
    "title": "MICROSOFT BUILD 2026: THE AGENT-FIRST ERA BEGINS",
    "highlight_word": "AGENT-FIRST",
    "category": "MICROSOFT BUILD 2026",
    "subtitle": "Every layer of the stack is going agent-native",
    "accent": "blue",
    "stats": [
        {"number": "7", "label": "New AI\nModels"},
        {"number": "50%", "label": "Azure Perf\nImprovement"},
        {"number": "1", "label": "Always-On\nPersonal Agent"},
        {"number": "100+", "label": "Announcements\nTotal"},
    ],
    "points": [
        {"title": "MICROSOFT SCOUT",
         "body": "Always-on personal agent. Plans, executes, follows up across your entire Microsoft stack. Not Copilot. What Copilot became."},
        {"title": "GITHUB COPILOT DESKTOP",
         "body": "Standalone agent-native app. Full project awareness, not line-by-line autocomplete. Building features, not suggesting code."},
        {"title": "PROJECT SOLARA",
         "body": "Windows redesigned FOR AI agents. Not AI added to Windows. The OS itself becomes agent-native. Biggest signal from Build."},
        {"title": "7 NEW AI MODELS",
         "body": "Enterprise-grade models from Mustafa Suleyman. Plus Mayo Clinic partnership for healthcare-specific foundation model."},
        {"title": "AZURE COBALT 200 VMS",
         "body": "50% performance boost, optimized for agentic workloads. Running AI agents at scale just got significantly cheaper."},
        {"title": "AGENT CONTROL SPEC",
         "body": "Open standard for portable agent governance. Solves 'how to control agents in production.' Works across any runtime."},
    ],
}


async def run(dry_run: bool = False):
    logger.info("Generating Microsoft Build 2026 infographic...")
    image_path = generate_infographic(
        title=INFOGRAPHIC_DATA["title"],
        points=INFOGRAPHIC_DATA["points"],
        category=INFOGRAPHIC_DATA["category"],
        subtitle=INFOGRAPHIC_DATA["subtitle"],
        highlight_word=INFOGRAPHIC_DATA["highlight_word"],
        accent=INFOGRAPHIC_DATA["accent"],
        stats=INFOGRAPHIC_DATA["stats"],
        branding_text="Follow for AI updates",
        filename="ms-build-2026-post.png",
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
            f"Published Microsoft Build 2026 post!\nPost ID: {result['post_id']}"
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
