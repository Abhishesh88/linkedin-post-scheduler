#!/usr/bin/env python3
"""Generate + publish NVIDIA Cosmos 3 post with infographic to LinkedIn."""
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

logger = setup_logging("publish_cosmos3")

POST_TEXT = """NVIDIA just open-sourced Cosmos 3.

A world foundation model that teaches robots and autonomous vehicles to think before they act.

This is not another chatbot. This is physical AI.

Here's why engineers should pay attention:

1. It generates actions, not just text

Cosmos 3 doesn't just describe what's in a scene. It outputs joint angles, gripper positions, and motion sequences. Robots learn to reach, grasp, move, and place objects from generated data.

No more hand-coding every movement. The model generates physically grounded actions.

2. Mixture-of-Transformers architecture

Two blocks working together: a Reasoner that interprets the scene and a Generator that creates multimodal outputs — text, video, images, ambient sound, and action data.

One model. Five output modalities.

3. The benchmark numbers are serious

Top-ranked on Artificial Analysis open weights leaderboards. First on Physics-IQ, R-Bench, PAI-Bench. First on VANTAGE-Bench for smart infrastructure and TAR challenge for traffic anomaly detection.

This isn't close. It's leading every physical AI benchmark.

4. Video generation for edge cases

The biggest problem in autonomous vehicles: how do you train for crashes, near-misses, and rare scenarios you can't safely recreate? Cosmos 3 generates physically plausible video sequences of exactly those situations.

Synthetic training data for the scenarios that matter most.

5. Already in production

Agile Robots uses it for humanoid training at scale. Linker Vision deploys it across thousands of camera feeds for city operations. Not a research paper. Deployed systems.

6. Open source, multiple sizes

Nano (16B params), Super (64B params), plus specialized variants for text-to-image, image-to-video, and robotic manipulation.

Available on Hugging Face. OpenMDW 1.1 license. Deploy via NVIDIA NIM.

8.3K stars on GitHub and growing fast.

The gap between digital AI and physical AI just got a lot smaller.

What would you build with a model that understands physics?

#NVIDIACosmos #PhysicalAI #Robotics #OpenSource #COMPUTEX2026"""

INFOGRAPHIC_DATA = {
    "title": "NVIDIA OPEN-SOURCES COSMOS 3: PHYSICAL AI THAT ACTS",
    "highlight_word": "COSMOS 3",
    "category": "OPEN SOURCE LAUNCH",
    "subtitle": "World foundation model for robots & autonomous vehicles",
    "accent": "teal",
    "stats": [
        {"number": "8.3K", "label": "GitHub\nStars"},
        {"number": "5", "label": "Output\nModalities"},
        {"number": "#1", "label": "Physics-IQ\nBenchmark"},
        {"number": "64B", "label": "Params\n(Super)"},
    ],
    "points": [
        {"title": "GENERATES ACTIONS, NOT TEXT",
         "body": "Outputs joint angles, gripper positions, motion sequences. Robots learn to reach, grasp, and place from generated data."},
        {"title": "MIXTURE-OF-TRANSFORMERS",
         "body": "Reasoner interprets scenes + Generator creates text, video, images, sound, and action data. One model, five modalities."},
        {"title": "DOMINATES EVERY BENCHMARK",
         "body": "#1 on Physics-IQ, R-Bench, PAI-Bench, VANTAGE-Bench, and TAR challenge. Leading all physical AI benchmarks."},
        {"title": "EDGE-CASE VIDEO GENERATION",
         "body": "Generates physically plausible crash, near-miss, and rare scenarios for autonomous vehicle training. No real-world risk."},
        {"title": "ALREADY IN PRODUCTION",
         "body": "Agile Robots: humanoid training at scale. Linker Vision: thousands of camera feeds for city operations. Deployed, not research."},
        {"title": "OPEN SOURCE, MULTIPLE SIZES",
         "body": "Nano 16B, Super 64B + specialized variants. Hugging Face, OpenMDW license, NVIDIA NIM deployment ready."},
    ],
}


async def run(dry_run: bool = False):
    logger.info("Generating NVIDIA Cosmos 3 infographic...")
    image_path = generate_infographic(
        title=INFOGRAPHIC_DATA["title"],
        points=INFOGRAPHIC_DATA["points"],
        category=INFOGRAPHIC_DATA["category"],
        subtitle=INFOGRAPHIC_DATA["subtitle"],
        highlight_word=INFOGRAPHIC_DATA["highlight_word"],
        accent=INFOGRAPHIC_DATA["accent"],
        stats=INFOGRAPHIC_DATA["stats"],
        branding_text="Follow for AI updates",
        filename="nvidia-cosmos3-post.png",
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
            f"Published NVIDIA Cosmos 3 post!\nPost ID: {result['post_id']}"
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
