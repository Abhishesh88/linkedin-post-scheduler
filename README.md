# LinkedIn Post Scheduler

An AI pipeline that drafts one high-quality LinkedIn post per day for an engineering
leader, then routes it through a human approval step before anything is published.

It discovers what's trending in AI/engineering, researches it, writes a post in a
defined voice, generates an infographic or finds a short video, queues it in Google
Sheets, and sends it to Telegram with approve/reject buttons.

## How it works

```
discover trending topic → research → generate post → image/video
        → write to Google Sheets → send to Telegram for approval
```

- **Discovery & research** — `src/researcher.py` (You.com search + GitHub trending API + Google Trends)
- **Generation** — `src/post_generator.py` + `config/prompts/system_prompt.txt` (voice, content pillars, hook patterns)
- **Media** — `src/image_generator.py` (Playwright infographics) / `src/video_finder.py`
- **Queue & approval** — `src/sheets_client.py`, `src/telegram_bot.py`
- **Entry point** — `generate.py`

## Content strategy

Posts are anchored in one of four pillars and written from an engineering-leadership
perspective (technical depth + a leader's take). See `config/prompts/system_prompt.txt`
for the full voice/formula spec.

## Setup

1. Copy the env template and fill in your own values:
   ```bash
   cp .env.example .env
   ```
2. (If using the auto-commenter) copy the config template:
   ```bash
   cp src/commenter/config.example.json src/commenter/config.json
   ```
3. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```
4. Run:
   ```bash
   python generate.py --dry-run   # preview without generating
   python generate.py             # generate today's post
   ```

## Configuration

All secrets are read from environment variables — see `.env.example` for the full list
(You.com, HuggingFace, Google Sheets service account, Telegram, LinkedIn). **Never commit
real credentials.** `.env`, `*cookies*.json`, `credentials/`, and `src/commenter/config.json`
are git-ignored.

## Scheduling

Runs daily via GitHub Actions (`.github/workflows/generate.yml`) during peak LinkedIn
hours. Public repositories get unlimited free Actions minutes. The job fails fast on a
model outage and the scheduler re-triggers; the "today already posted" check keeps re-runs
idempotent. Required Actions secrets are listed in the workflow file.

## Note

Anything that posts, comments, or connects on your behalf can violate LinkedIn's Terms of
Service and risk your account. This project keeps a human approval step before publishing —
keep it that way.

## License

MIT — see [LICENSE](LICENSE).
