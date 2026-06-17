# LinkedIn Post Scheduler — Design Spec

## Overview

Automated LinkedIn post generation system for a **Software Engineering Manager** persona. Researches trending topics via You.com API, generates posts using HuggingFace Qwen3-235B, stages them in Google Sheets, sends for approval via Telegram with interactive buttons, and auto-publishes to LinkedIn on schedule.

Deployed entirely via **GitHub Actions** — no servers.

## Persona

- **Role**: Software Engineering Manager
- **Voice**: Conversational, expert, first-person. Shares lessons from leading engineering teams — hiring, delivery, culture, technical decision-making.
- **Audience**: Engineering leaders, senior engineers, tech professionals on LinkedIn
- **Default CTA style**: Soft question (e.g., "What's worked for your team?")

## Default Theme Bank

| Theme | Category |
|-------|----------|
| Engineering leadership lessons | Leadership |
| Hiring and interviewing engineers | Hiring |
| Team culture and psychological safety | Culture |
| Technical debt and prioritization | Technical |
| 1:1s and performance management | Management |
| Shipping fast vs. shipping right | Delivery |
| Growing senior engineers | Mentorship |
| Cross-functional collaboration | Collaboration |
| Incident response and blameless postmortems | Operations |
| Remote/hybrid engineering teams | Remote work |
| Architecture decisions and trade-offs | Technical |
| Onboarding new engineers | Onboarding |
| Managing up and stakeholder communication | Communication |
| Burnout and sustainable pace | Wellbeing |
| Career growth from IC to manager | Career |
| System design principles and patterns | System Design |
| Distributed systems and scalability | System Design |
| Microservices vs. monolith trade-offs | System Design |
| AI engineering in production | AI Engineering |
| Building RAG pipelines and retrieval systems | AI Engineering |
| LLM integration patterns for engineering teams | AI Engineering |
| Vector databases and embedding strategies | AI Engineering |
| AI agents and agentic workflows | AI Engineering |
| Prompt engineering best practices | AI Engineering |
| MLOps and model deployment | AI Engineering |
| Evaluating and testing AI systems | AI Engineering |
| Fine-tuning vs. RAG vs. prompt engineering | AI Engineering |
| API design and developer experience | System Design |
| Event-driven architecture | System Design |
| Caching strategies and performance optimization | System Design |

## Architecture

```
GitHub Actions (3 cron workflows)
  │
  ├─ generate.yml (Monday 06:00 UTC)
  │    → research.py: You.com topic + LinkedIn competitor research
  │    → post_generator.py: Qwen3-235B generates 5 posts
  │    → sheets_client.py: writes drafts to Google Sheets
  │    → telegram_bot.py: sends posts with Approve/Reject buttons
  │
  ├─ approval-poll.yml (every 15 min)
  │    → poll_approvals.py: Telegram getUpdates → update Sheets
  │
  └─ publish.yml (weekdays 09:00 UTC)
       → publish.py: reads approved posts → LinkedIn API → update Sheets
       → telegram_bot.py: sends "Published!" confirmation
```

## Google Sheets Structure

### Tab 1: Settings (single row)

| Column | Example |
|--------|---------|
| voice | conversational, expert, first-person |
| audience | engineering leaders, senior engineers |
| cta_style | soft question |
| hashtags | (empty unless specified) |

### Tab 2: Theme Bank

| Column | Type | Description |
|--------|------|-------------|
| theme | string | Topic name |
| category | string | Grouping label |
| active | boolean | TRUE/FALSE — inactive themes are skipped |

### Tab 3: Posts

| Column | Type | Description |
|--------|------|-------------|
| week_start | date (ISO) | Monday of the target week |
| day | date (ISO) | Scheduled post date |
| theme | string | Assigned theme |
| draft_text | string | Generated post content |
| char_count | int | Character count |
| research_summary | string | Key research findings used |
| status | string | draft → pending_approval → approved → rejected → published |
| suggested_time | string | Default "09:00 UTC" |
| telegram_msg_id | int | For callback tracking |
| feedback | string | Rejection reason or edit notes |
| linkedin_post_id | string | After publishing |
| published_at | datetime | Actual publish timestamp |

## Research Strategy (You.com API)

Per theme, 4 queries:

1. **Topic trends**: `"{theme}" software engineering 2026 trends insights`
2. **LinkedIn competitor posts**: `site:linkedin.com "{theme}" engineering manager`
3. **Audience-specific**: `"{theme}" engineering leadership tips strategies`
4. **Data/stats**: `"{theme}" software engineering statistics data 2026`

Research output is a condensed summary (max 3000 chars per theme) fed into the Qwen prompt.

## Post Generation (Qwen3-235B via HuggingFace)

### System Prompt

```
You are a LinkedIn ghostwriter for a Software Engineering Manager. Write posts that:
- Are 80-200 words, formatted for LinkedIn (short paragraphs, line breaks between ideas)
- Use a conversational, expert, first-person voice
- Share real-world lessons from leading engineering teams
- End with a soft question CTA
- Never fabricate statistics — use [placeholder] brackets for unverified data
- Avoid generic advice — be specific and opinionated
- No hashtags unless explicitly provided
- No emojis unless they add meaning (max 2 per post)
```

### User Prompt (per post)

```
Theme: {theme}
Day: {day} ({weekday})
Research context:
{research_summary}

Prior posts this week (avoid overlap):
{prior_posts_this_week}

Last 5 published posts (avoid semantic duplication):
{prior_published}

Generate one LinkedIn post. Return ONLY the post text, nothing else.
```

### Deduplication

After generation, compare each draft against:
1. Other posts in the same week (avoid repetitive structure)
2. Last 5 published posts from Sheets (semantic similarity check via Qwen)

If >70% similar, regenerate with prompt: "The previous draft was too similar to: '{similar_post_opening}'. Take a completely different angle on {theme}."

## Telegram Integration

### Sending Drafts

For each generated post, send a Telegram message:

```
📝 LinkedIn Draft — {weekday}, {date}
Theme: {theme}

---
{draft_text}
---

📊 {char_count} chars | ⏰ Scheduled: {suggested_time}

[✅ Approve]  [❌ Reject]
```

Inline keyboard buttons send callback data: `approve_{post_row}` / `reject_{post_row}`.

### Handling Callbacks

- **Approve**: Update Sheets status to `approved`, reply "Approved for {date}"
- **Reject**: Update Sheets status to `rejected`, reply "What should change?" and store the next text message as feedback

## LinkedIn Publishing

Uses LinkedIn Marketing API v2 (`/rest/posts` endpoint).

### Auth Flow

- LinkedIn OAuth 2.0 — 3-legged flow performed once manually to get a long-lived access token
- Token stored as GitHub Secret `LINKEDIN_ACCESS_TOKEN`
- Refresh token flow included for token renewal

### Post API Call

```
POST https://api.linkedin.com/rest/posts
Authorization: Bearer {access_token}
X-Restli-Protocol-Version: 2.0.0

{
  "author": "urn:li:person:{person_id}",
  "lifecycleState": "PUBLISHED",
  "visibility": "PUBLIC",
  "commentary": "{draft_text}",
  "distribution": {
    "feedDistribution": "MAIN_FEED"
  }
}
```

## GitHub Actions Workflows

### 1. generate.yml

```yaml
on:
  schedule:
    - cron: '0 6 * * 1'  # Monday 06:00 UTC
  workflow_dispatch: {}    # Manual trigger
```

Steps: checkout → setup Python → install deps → run `python generate.py`

### 2. approval-poll.yml

```yaml
on:
  schedule:
    - cron: '*/15 * * * *'  # Every 15 minutes
  workflow_dispatch: {}
```

Steps: checkout → setup Python → install deps → run `python poll_approvals.py`

### 3. publish.yml

```yaml
on:
  schedule:
    - cron: '0 9 * * 1-5'  # Weekdays 09:00 UTC
  workflow_dispatch: {}
```

Steps: checkout → setup Python → install deps → run `python publish.py`

## Project Structure

```
linkedin-post-scheduler/
├── .github/
│   └── workflows/
│       ├── generate.yml
│       ├── approval-poll.yml
│       └── publish.yml
├── src/
│   ├── __init__.py
│   ├── search_client.py        # You.com API with key rotation
│   ├── llm_client.py           # Qwen3-235B via HuggingFace
│   ├── researcher.py           # Topic + competitor research
│   ├── post_generator.py       # Post generation + dedup
│   ├── sheets_client.py        # Google Sheets 3-tab integration
│   ├── telegram_bot.py         # Send drafts, handle callbacks
│   ├── linkedin_publisher.py   # LinkedIn API posting
│   └── utils.py
├── config/
│   └── prompts/
│       ├── system_prompt.txt
│       └── post_prompt.txt
├── generate.py                 # Entry: research → generate → sheets → telegram
├── poll_approvals.py           # Entry: poll Telegram → update sheets
├── publish.py                  # Entry: publish approved → LinkedIn
├── requirements.txt
├── .env.example
└── .gitignore
```

## Dependencies

```
httpx>=0.27.0
aiohttp>=3.9.0
pyyaml>=6.0
python-dotenv>=1.0.0
gspread>=6.0.0
google-auth>=2.0.0
youdotcom>=0.6.0
python-telegram-bot>=21.0
```

## Environment Variables / GitHub Secrets

| Variable | Source |
|----------|--------|
| YOU_API_KEYS | From content-generator (.env) |
| HF_API_KEY | From content-generator (.env) |
| HF_MODEL | Qwen/Qwen3-235B-A22B |
| HF_API_URL | https://router.huggingface.co/v1/chat/completions |
| GOOGLE_SHEETS_CREDENTIALS | Service account JSON string |
| GOOGLE_SHEET_ID | New sheet for this project |
| TELEGRAM_BOT_TOKEN | From @BotFather |
| TELEGRAM_CHAT_ID | Your Telegram chat/group ID |
| LINKEDIN_ACCESS_TOKEN | From LinkedIn OAuth |
| LINKEDIN_PERSON_ID | Your LinkedIn person URN |

## Guardrails

1. Never publish directly — all posts go through `pending_approval` status
2. Never fabricate statistics — use `[placeholder]` brackets
3. Each post under 3,000 chars (LinkedIn limit), warn if over 1,500
4. No hashtags unless `hashtags` field in Settings tab is populated
5. Dedup against last 5 published posts
6. Log every action: theme assignment, generation, dedup check, regeneration
7. If theme bank is empty, fail with clear error
8. If settings are contradictory, send clarification request to Telegram instead of guessing

## Setup Checklist

1. Create Google Sheet with 3 tabs (Settings, Theme Bank, Posts)
2. Populate Settings row and Theme Bank with default themes
3. Create Telegram bot via @BotFather, get token
4. Get your Telegram chat ID
5. Create LinkedIn Developer App, complete OAuth flow, get access token
6. Add all secrets to GitHub repository settings
7. Enable GitHub Actions workflows
