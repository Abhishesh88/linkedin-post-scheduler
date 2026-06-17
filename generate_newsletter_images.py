#!/usr/bin/env python3
"""Generate all newsletter section images."""
import sys
sys.path.insert(0, ".")
from src.image_generator import generate_infographic

# Cover image
generate_infographic(
    title="AI ENGINEERING WEEKLY: MAY 25, 2026",
    highlight_word="MAY 25, 2026",
    category="WEEKLY NEWSLETTER",
    subtitle="Tools, Repos & Signals That Matter",
    accent="orange",
    stats=[
        {"number": "6", "label": "Top Stories"},
        {"number": "2", "label": "Trending\nRepos"},
        {"number": "5", "label": "Signals"},
        {"number": "6min", "label": "Read\nTime"},
    ],
    points=[
        {"title": "GROK BUILD BETA LAUNCHES",
         "body": "xAI's terminal coding agent with Plan Mode, parallel subagents, and image/video generation."},
        {"title": "BUMBLEBEE SECURITY SCANNER",
         "body": "Perplexity open-sources free tool to detect malicious extensions, MCP configs, and packages."},
        {"title": "ZOZO 180M CONTACT SOLVER",
         "body": "Open-source GPU physics engine for cloth simulation without clipping."},
        {"title": "QWEN 27B JAILBROKEN TO 4%",
         "body": "Safety guardrails stripped with zero capability loss. Alignment needs a rethink."},
        {"title": "CODING AGENTS FAIL REAL DBS",
         "body": "30% pass rate drop when real PostgreSQL/Redis added to benchmarks."},
        {"title": "GOOGLE ANTIGRAVITY CLI",
         "body": "Google enters terminal AI agents. Every major company building for your terminal now."},
    ],
    branding_text="Subscribe for weekly updates",
    filename="newsletter-cover.png",
)
print("1. Cover image done")

# Top News - Grok Build
generate_infographic(
    title="xAI OPENS GROK BUILD BETA",
    highlight_word="GROK BUILD",
    category="TOP NEWS",
    subtitle="Terminal-native coding agent with CLI automations",
    accent="purple",
    stats=[
        {"number": "1", "label": "Curl Command\nTo Install"},
        {"number": "50", "label": "Free Daily\nRequests"},
        {"number": "$300", "label": "Full Access\nPer Month"},
        {"number": "3x", "label": "Faster\nRefactors"},
    ],
    points=[
        {"title": "PLAN MODE FIRST",
         "body": "Shows full plan before touching code. You review, edit, reorder, then approve execution."},
        {"title": "PARALLEL SUBAGENTS",
         "body": "Multiple AI processes work simultaneously. One scans deps, another writes code, a third runs tests."},
        {"title": "ARENA MODE",
         "body": "Edits files then shows alternative implementations. You pick the best approach."},
        {"title": "MCP + SKILLS BUILT IN",
         "body": "Connects to databases, CI/CD, external tools. Reads existing CLAUDE.md with no changes needed."},
        {"title": "IMAGE + VIDEO FROM CLI",
         "body": "Generate media assets directly from terminal. No browser, no separate tool needed."},
        {"title": "HEADLESS CI MODE",
         "body": "Use -p flag to plug into pipelines and automated scripts. Full automation support."},
    ],
    branding_text="AI Engineering Weekly",
    filename="newsletter-topnews-grok.png",
)
print("2. Top News image done")

# Top Repo 1 - Bumblebee
generate_infographic(
    title="PERPLEXITY OPEN-SOURCES BUMBLEBEE",
    highlight_word="BUMBLEBEE",
    category="TOP REPO",
    subtitle="Free security tool for AI developers",
    accent="red",
    stats=[
        {"number": "160+", "label": "Poisoned\nPackages"},
        {"number": "12M", "label": "Weekly\nDownloads Hit"},
        {"number": "5", "label": "Browsers\nScanned"},
        {"number": "$0", "label": "Apache 2.0\nLicense"},
    ],
    points=[
        {"title": "BROWSER EXTENSION SCANNER",
         "body": "Scans Chrome, Edge, Brave, Arc, Firefox extensions plus VS Code editor plugins for malicious code."},
        {"title": "MCP CONFIG AUDITOR",
         "body": "Checks local AI assistant settings that control access to emails, databases, and code repos."},
        {"title": "PACKAGE VULNERABILITY SCAN",
         "body": "Detects vulnerable packages across npm, PyPI, Go without executing package managers."},
        {"title": "READ-ONLY SAFE SCAN",
         "body": "Reads config files without running anything. Cannot accidentally trigger malicious code."},
    ],
    branding_text="AI Engineering Weekly",
    filename="newsletter-repo-bumblebee.png",
)
print("3. Top Repo Bumblebee image done")

# Top Repo 2 - ZOZO
generate_infographic(
    title="ZOZO OPEN-SOURCES CLOTH PHYSICS SOLVER",
    highlight_word="CLOTH PHYSICS",
    category="TOP REPO",
    subtitle="180M+ contact points without clipping",
    accent="blue",
    stats=[
        {"number": "180M+", "label": "Contact\nPoints"},
        {"number": "$0.50", "label": "Per Hour\nGPU Cost"},
        {"number": "1GB", "label": "Docker\nImage"},
        {"number": "0%", "label": "Clipping\nRate"},
    ],
    points=[
        {"title": "GPU-ACCELERATED PHYSICS",
         "body": "Handles 180M+ contact points in a single scene. Fabric never clips through itself."},
        {"title": "PYTHON API + JUPYTERLAB",
         "body": "Write simulation code in browser notebooks. Full Python integration built in."},
        {"title": "CLOUD-READY DEPLOYMENT",
         "body": "Docker image, Windows .exe, ready for AWS, GCP, RunPod. Rent GPU for $0.50/hr on vast.ai."},
        {"title": "BLENDER ADD-ONS AVAILABLE",
         "body": "Community already built Blender integrations. Production-ready for fashion and game studios."},
    ],
    branding_text="AI Engineering Weekly",
    filename="newsletter-repo-zozo.png",
)
print("4. Top Repo ZOZO image done")

# Signals
generate_infographic(
    title="THIS WEEK'S AI SIGNALS",
    highlight_word="SIGNALS",
    category="SIGNALS",
    subtitle="5 developments every engineer should know",
    accent="teal",
    stats=[
        {"number": "4%", "label": "Qwen 27B\nRefusal Rate"},
        {"number": "30%", "label": "Agent Pass\nRate Drop"},
        {"number": "MIT", "label": "LongCat\nLicense"},
        {"number": "128GB", "label": "Local Model\nRAM"},
    ],
    points=[
        {"title": "QWEN 27B JAILBROKEN TO 4%",
         "body": "Pliny strips safety guardrails with zero capability loss. Model alignment needs application-level defense."},
        {"title": "CODING AGENTS FAIL REAL DBS",
         "body": "30% pass rate drop with real PostgreSQL/Redis. Demand real infrastructure in your agent benchmarks."},
        {"title": "LONGCAT FREE AVATAR MODEL",
         "body": "MIT-licensed talking avatar that may beat commercial alternatives. Default starting point for AI faces."},
        {"title": "LOCAL MODEL BEATS CLOUD",
         "body": "New coding model beats Qwen and DeepSeek on 128GB RAM machines. No GPU required."},
        {"title": "GOOGLE ANTIGRAVITY CLI",
         "body": "Google enters terminal AI agents. Every major AI company now building for your terminal."},
    ],
    branding_text="AI Engineering Weekly",
    filename="newsletter-signals.png",
)
print("5. Signals image done")

print("\nAll newsletter images generated in output/images/")
