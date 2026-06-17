#!/usr/bin/env python3
"""Generate AI Engineering Weekly newsletter + infographic, publish to LinkedIn + send to Telegram."""
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

logger = setup_logging("newsletter")

# LinkedIn post version (short, hooks to newsletter)
POST_TEXT = """AI Engineering Weekly — May 25, 2026

This week's biggest stories in AI engineering:

1. xAI opens Grok Build beta — a terminal-native coding agent with Plan Mode, parallel subagents, image/video generation, and CLI automations. Install with one curl command. $300/mo or 50 free daily requests.

2. Perplexity open-sources Bumblebee — a free security tool that scans for malicious browser extensions, MCP configs, and vulnerable packages across npm, PyPI, and Go. Apache 2.0 license.

3. ZOZO open-sources ppf-contact-solver — handles 180M+ clothing contact points on GPU without clipping. Python API + JupyterLab + Docker. Run on vast.ai for $0.50/hr.

4. Pliny jailbreaks Qwen 27B down to 4% refusal rate with zero capability loss. Model safety researchers need to pay attention.

5. New benchmark shows coding agents lose 30% pass rate when real databases are added. Your agent demos are lying to you.

6. Google Antigravity ships a terminal CLI to run AI agents from the command line. The terminal is the new IDE.

The AI coding agent wars are heating up:
Claude Code vs Grok Build vs Codex CLI vs Cursor vs Google Antigravity.

Every developer will have a terminal-native AI agent by end of year. The question is which one.

Full newsletter in the comments. Save this for later.

#AIEngineering #GrokBuild #ClaudeCode #DeveloperTools #OpenSource"""

# Full newsletter for Telegram (user pastes into LinkedIn newsletter editor)
FULL_NEWSLETTER = """AI ENGINEERING WEEKLY — May 25, 2026

Read time: 6 min 35 sec

SUMMARY

Top News
→ xAI opens Grok Build beta with image generation, video, and CLI automations

Top Repo
→ Perplexity open-sources free security tool that protects developers from malicious AI coding tools

Top Repo
→ ZOZO open-sources a physics solver that handles 180M clothing contacts without clipping

Signals
1. Pliny jailbreaks Qwen 27B down to 4% refusal rate with zero capability loss
2. New benchmark shows coding agents lose 30% pass rate when real databases are added
3. LongCat drops a free MIT-licensed talking avatar model that may beat all others
4. New local coding model beats Qwen and DeepSeek on 128 GB RAM machines
5. Google Antigravity ships a terminal CLI to run AI agents from the command line

---

TOP NEWS

xAI opens Grok Build beta with image generation, video, and CLI automations

xAI just dropped Grok Build, a coding agent that lives in your terminal and actually takes action on your codebase. Not a chatbot. Not autocomplete. An agent that reads your project, makes a plan, edits files, and runs commands.

The biggest problem with AI coding tools? They start executing and go off the rails before you notice. Grok Build solves this with Plan Mode: the agent shows you the full plan first, you approve each step, and nothing gets touched until you say so.

Here is what you can do with it:

→ Run parallel subagents that split complex tasks and work simultaneously across your repo
→ Use headless mode with a -p flag to plug it into CI pipelines and automated scripts
→ Extend it with Skills, hooks, and MCP servers — it already reads your existing CLAUDE.md with no changes needed
→ Install it with one command: curl -fsSL https://x.ai/cli/install.sh | bash

Available now for SuperGrok subscribers. Free tier gets 50 daily requests.

---

TOP REPO #1

Perplexity open-sources Bumblebee — free security tool for developers

Hackers have been quietly poisoning free software packages that almost every app is built on. One group alone injected malicious code into over 160 packages, including a React tool with roughly 12 million weekly downloads. Install one, and attackers get a backdoor into everything you touch, including your AI tools.

Perplexity just open-sourced their fix. It's called Bumblebee, the same tool they use internally to protect their own team.

Here's what it scans:

→ Browser extensions across Chrome, Edge, Brave, Arc, and Firefox, plus editor plugins in VS Code and its forks
→ MCP config files — the local settings that tell AI assistants which external services they can access
→ Vulnerable packages across npm, PyPI, Go, and more, without executing package managers or touching your credentials

It uses a read-only scan, reading config files without running anything, so it can't accidentally trigger the malicious code it's looking for. Free, on GitHub, Apache 2.0 license.

---

TOP REPO #2

ZOZO open-sources ppf-contact-solver — 180M+ clothing contacts without clipping

Ever seen a cloth simulation where a shirt clips through itself like a ghost? That's the problem ZOZO, Japan's largest fashion e-commerce company, just open-sourced a fix for.

They released ppf-contact-solver, a physics simulation tool that handles how fabric, ropes, and soft objects touch and collide. Objects never clip through each other, and fabric never stretches beyond a strict limit you set.

The numbers are serious:

→ 180M+ contact points handled in a single scene, all running on the GPU
→ Python API with JupyterLab built in
→ Docker image (~1GB), Windows .exe, and cloud-ready for AWS, GCP, RunPod
→ You can rent a GPU for under $0.50/hour on vast.ai and run it remotely

---

SIGNALS

1. Pliny jailbreaks Qwen 27B down to 4% refusal rate with zero capability loss
2,445 Likes
If safety guardrails can be stripped this easily without degrading the model, we need to seriously rethink how we evaluate model alignment. This isn't theoretical — it's a working fine-tune anyone can replicate.

2. New benchmark shows coding agents lose 30% pass rate when real databases are added
498 Likes
Most coding agent demos use toy examples. When you add real PostgreSQL, Redis, or S3 into the test suite, pass rates crater. If you're evaluating agents for production, demand benchmarks with real infrastructure.

3. LongCat drops a free MIT-licensed talking avatar model that may beat all others
1,725 Likes
Free, MIT-licensed, and competitive with commercial alternatives. If you're building customer-facing AI with a visual presence, this just became the default starting point.

4. New local coding model beats Qwen and DeepSeek on 128 GB RAM machines
777 Likes
For teams that can't send code to cloud APIs due to compliance or IP concerns, this is the best local option yet. Runs entirely on-device, no GPU required if you have enough RAM.

5. Google Antigravity ships a terminal CLI to run AI agents from the command line
1,386 Likes
Google is also entering the terminal-native AI agent space. The convergence is clear — every major AI company is building coding agents that live in your terminal, not your browser.

---

That's it for this week. Reply with what you're building — I read every response.

Abhishesh"""


INFOGRAPHIC_DATA = {
    "title": "AI ENGINEERING WEEKLY: TOP STORIES MAY 25",
    "highlight_word": "TOP STORIES",
    "category": "WEEKLY NEWSLETTER",
    "subtitle": "The biggest AI engineering news this week",
    "accent": "orange",
    "stats": [
        {"number": "6", "label": "Top Stories\nThis Week"},
        {"number": "180M", "label": "Contact Points\nin ZOZO Solver"},
        {"number": "30%", "label": "Agent Pass\nRate Drop"},
        {"number": "$0", "label": "Bumblebee\nSecurity Tool"},
    ],
    "points": [
        {"title": "GROK BUILD BETA LAUNCHES",
         "body": "xAI's terminal coding agent with Plan Mode, parallel subagents, image/video gen. One curl install. $300/mo or 50 free requests."},
        {"title": "PERPLEXITY OPEN-SOURCES BUMBLEBEE",
         "body": "Free security scanner for malicious browser extensions, MCP configs, and npm/PyPI packages. Apache 2.0 license."},
        {"title": "ZOZO 180M CONTACT SOLVER",
         "body": "Open-source physics engine for cloth simulation. No clipping, GPU-accelerated, Python API, runs on $0.50/hr cloud GPU."},
        {"title": "QWEN 27B JAILBROKEN TO 4%",
         "body": "Pliny strips safety guardrails with zero capability loss. Model alignment needs a serious rethink."},
        {"title": "CODING AGENTS FAIL REAL DBS",
         "body": "New benchmark: agents lose 30% pass rate when real PostgreSQL/Redis are added. Demo benchmarks are lying."},
        {"title": "GOOGLE ANTIGRAVITY CLI",
         "body": "Google enters terminal AI agents. Every major AI company is building coding agents for your terminal now."},
    ],
}


async def run(dry_run: bool = False):
    # 1. Generate infographic
    logger.info("Generating newsletter infographic...")
    image_path = generate_infographic(
        title=INFOGRAPHIC_DATA["title"],
        points=INFOGRAPHIC_DATA["points"],
        category=INFOGRAPHIC_DATA["category"],
        subtitle=INFOGRAPHIC_DATA["subtitle"],
        highlight_word=INFOGRAPHIC_DATA["highlight_word"],
        accent=INFOGRAPHIC_DATA["accent"],
        stats=INFOGRAPHIC_DATA["stats"],
        branding_text="Subscribe to newsletter",
        filename="newsletter-may25.png",
    )
    logger.info("Infographic: %s", image_path)

    if dry_run:
        logger.info("[DRY RUN] Image: %s", image_path)
        logger.info("Post: %d chars", len(POST_TEXT))
        logger.info("Newsletter: %d chars", len(FULL_NEWSLETTER))
        return

    # 2. Publish post to LinkedIn with infographic
    logger.info("Publishing to LinkedIn...")
    result = await publish_post(text=POST_TEXT, image_path=image_path)

    if result["success"]:
        logger.info("PUBLISHED! Post ID: %s", result["post_id"])
    else:
        logger.error("Publish failed: %s", result["error"])

    # 3. Send full newsletter to Telegram for copy-paste into LinkedIn newsletter editor
    logger.info("Sending full newsletter to Telegram...")
    parts = []
    current = ""
    for line in FULL_NEWSLETTER.split("\n"):
        if len(current) + len(line) + 1 > 3900:
            parts.append(current)
            current = ""
        current += line + "\n"
    parts.append(current)

    for i, part in enumerate(parts):
        header = f"NEWSLETTER Part {i+1}/{len(parts)}:\n\n" if len(parts) > 1 else "FULL NEWSLETTER (paste into LinkedIn newsletter editor):\n\n"
        await telegram_bot.send_notification(header + part)
        logger.info("Sent part %d/%d to Telegram", i + 1, len(parts))

    await telegram_bot.send_notification(
        f"LinkedIn post published: {result.get('post_id', 'N/A')}\n\n"
        f"Newsletter sent above — paste into LinkedIn newsletter editor."
    )
    logger.info("Done!")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    asyncio.run(run(dry_run=args.dry_run))


if __name__ == "__main__":
    main()
