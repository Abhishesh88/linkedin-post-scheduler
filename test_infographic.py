"""Quick test — generate 3 infographic images matching viral LinkedIn style."""

import sys
sys.path.insert(0, ".")

from src.image_generator import generate_infographic

# Post 1: Personal Story + Setup (6 cards, 3-col grid, orange accent)
path1 = generate_infographic(
    title="HOW I REPLACED MY ENTIRE DEV WORKFLOW WITH CLAUDE CODE",
    points=[
        {"title": "Terminal-First, Not IDE",
         "body": "Claude Code runs in your terminal. It sees your entire codebase, not just the open file. Full project awareness from day one."},
        {"title": "CLAUDE.md Secret Weapon",
         "body": "Drop a CLAUDE.md at your project root. Coding conventions, stack preferences, rules. Zero repeat instructions ever again."},
        {"title": "Let It Run Autonomously",
         "body": "Old: prompt > read > copy > test > repeat. New: describe what you want > Claude edits files, runs tests, commits. 4 hrs to 40 min."},
        {"title": "MCP Connectors",
         "body": "Claude Code talks to GitHub, your database, your APIs directly. No more tab switching. It reads, fixes, and pushes."},
        {"title": "Extended Thinking Mode",
         "body": "Toggle Opus with Extended Thinking for architecture decisions. It thinks for 30 seconds, delivers senior-level system design."},
        {"title": "3x Faster Shipping",
         "body": "70% fewer bugs in code review. Mass-deleted Copilot, ChatGPT for code, and 4 VS Code extensions. One tool to rule them all."},
    ],
    category="DEV WORKFLOW",
    subtitle="5 steps that changed everything",
    highlight_word="CLAUDE CODE",
    accent="orange",
    stats=[
        {"number": "3x", "label": "Faster\nShipping"},
        {"number": "70%", "label": "Fewer Bugs\nin Review"},
        {"number": "40m", "label": "vs 4 Hours\nPer Feature"},
        {"number": "6", "label": "Tools\nReplaced"},
    ],
    branding_text="Follow for more AI tips",
    filename="post1-dev-workflow-v2.png",
)
print(f"Post 1: {path1}")

# Post 2: News Hook (6 cards, 3-col, blue accent)
path2 = generate_infographic(
    title="CLAUDE CODE /GOAL MODE CHANGES EVERYTHING",
    points=[
        {"title": "Give Goals, Not Tasks",
         "body": "Don't micromanage. Say 'make this app production-ready.' Claude breaks it into subtasks, prioritizes, and executes."},
        {"title": "Auto Task Planning",
         "body": "Builds a task tree automatically. Plans before coding. No blind generation. Structured, thoughtful execution."},
        {"title": "Self-Recovery From Errors",
         "body": "Hits a bug? Debugs itself. Tries a different approach. No more babysitting. It recovers and moves on."},
        {"title": "Knows When To Stop",
         "body": "Doesn't loop forever. Ships a working solution or asks for help. No infinite retry cycles."},
        {"title": "Solo Founders Win Big",
         "body": "Your 2-week sprint just became 2 days. Build MVPs at 10x speed with zero team overhead."},
        {"title": "Teams Get 24/7 Dev",
         "body": "Your team gets a junior dev that never sleeps, never needs onboarding, and works on weekends."},
    ],
    category="BREAKING AI UPDATE",
    subtitle="The autonomous coding revolution",
    highlight_word="/GOAL MODE",
    accent="blue",
    stats=[
        {"number": "10x", "label": "Faster\nMVP Build"},
        {"number": "24/7", "label": "Autonomous\nCoding"},
        {"number": "40+", "label": "Files Changed\nPer Session"},
        {"number": "0", "label": "Babysitting\nNeeded"},
    ],
    branding_text="Follow for AI updates",
    filename="post2-goal-mode-v2.png",
)
print(f"Post 2: {path2}")

# Post 3: Tips (5 cards, 2-col + teal accent)
path3 = generate_infographic(
    title="5 CLAUDE CODE TRICKS THAT SAVED ME 20+ HOURS THIS WEEK",
    points=[
        {"title": "Read Codebase First",
         "body": "Before any task: 'Explore the codebase. Understand the architecture.' Takes 60 seconds. Saves hours of wrong assumptions."},
        {"title": "One-Shot Test Generation",
         "body": "Point at any file: 'Write comprehensive tests. Cover edge cases. Run them.' Monday: 0% coverage to 87% in 45 minutes."},
        {"title": "The Refactor Chain",
         "body": "'Refactor this module. Update every file that imports from it. Run all tests.' 15 files updated. Zero broken imports."},
        {"title": "Git Commits on Autopilot",
         "body": "After any change: 'Commit with conventional commits format.' Git log went from 'fix stuff' to searchable, structured history."},
        {"title": "Debug With Full Context",
         "body": "'This test is failing. Read test + source, figure out why, fix it.' A 2-hour team bug fixed in 4 minutes."},
    ],
    category="PRODUCTIVITY TIPS",
    subtitle="Tested and measured results",
    highlight_word="20+ HOURS",
    accent="teal",
    stats=[
        {"number": "23h", "label": "Saved\nPer Week"},
        {"number": "87%", "label": "Test Coverage\nin 45 Min"},
        {"number": "15", "label": "Files Auto\nRefactored"},
        {"number": "4m", "label": "Bug Fix vs\n2 Hours"},
    ],
    branding_text="Save this post",
    filename="post3-tricks-v2.png",
)
print(f"Post 3: {path3}")

print("\nAll 3 infographics generated! Check output/images/")
