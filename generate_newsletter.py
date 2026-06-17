#!/usr/bin/env python3
"""Weekly newsletter: AlphaSignal-style AI Engineering Weekly with Top News, Top Repos, and Signals."""
from __future__ import annotations

import asyncio
import json
import logging
import os
import re
from datetime import date

from dotenv import load_dotenv
load_dotenv()

from src.utils import setup_logging
from src.search_client import YouSearchClient
from src.llm_client import LLMClient
from src import telegram_bot

logger = setup_logging("newsletter")

# Research queries for different sections
NEWS_QUERIES = [
    "AI tools launched this week 2026",
    "Claude Anthropic announcement this week 2026",
    "OpenAI news this week 2026",
    "Google Gemini AI update this week 2026",
    "AI coding agents news this week 2026",
]

REPO_QUERIES = [
    "github trending AI tools this week 2026",
    "github trending open source AI agents 2026",
    "github trending developer tools AI this week 2026",
]

SIGNAL_QUERIES = [
    "AI model released open source this week 2026",
    "AI startup funding launch this week 2026",
    "AI engineering tool update this week 2026",
    "LLM benchmark new results this week 2026",
]

NEWSLETTER_PROMPT = """You are Abhishesh Mishra, Associate Director of Engineering, writing your weekly newsletter "AI Engineering Weekly" for engineering leaders.

Use the research below as RAW FACTS only. Write your OWN original analysis, opinions, and engineering takeaways. Do NOT copy headlines or text from the sources. Rewrite everything in your own voice as a senior engineer who tests and evaluates these tools.

RESEARCH (raw facts to use — rewrite in your own words):
{research}

GITHUB TRENDING (raw data — analyze in your own words):
{github_data}

Write the newsletter with these EXACT sections:

---

SUMMARY
Read time: 5 min

Top News
→ [your own one-line take on the biggest AI news]

Top Repo
→ [your own one-line take on the most interesting trending repo]

Signals
1. [your summary of signal 1]
2. [your summary of signal 2]
3. [your summary of signal 3]
4. [your summary of signal 4]
5. [your summary of signal 5]

---

TOP NEWS

[Your own headline — not copied from source]
Source: [URL]

[Write 2-3 paragraphs of ORIGINAL analysis. What happened, why it matters for engineering teams, what you would do about it. Share your engineering perspective — not a press release summary. Include specific technical details.]

---

TOP REPO

[Repo name] — [stars] Stars
[GitHub URL]

[Write 2-3 paragraphs of ORIGINAL analysis. What problem does it solve, how does it compare to alternatives, who should use it and who shouldn't. Give your honest engineering assessment.]

---

SIGNALS

For each signal, write a SHORT original take (2-3 sentences) on why it matters. Include the source URL.

1. [Your headline] — [metric]
   [Your original take + source URL]

2. [Your headline] — [metric]
   [Your original take + URL]

3. [Your headline] — [metric]
   [Your original take + URL]

4. [Your headline] — [metric]
   [Your original take + URL]

5. [Your headline] — [metric]
   [Your original take + URL]

---

That's it for this week. Reply to this newsletter with what you're building — I read every response.

Abhishesh

RULES:
- Write ORIGINAL analysis — do NOT copy headlines or text from sources
- Your voice: experienced engineer sharing honest opinions, not a news aggregator
- Be opinionated — say what's overhyped, what's underrated, what you'd actually use
- Include source URLs for reference but the analysis must be yours
- Name specific tools, versions, star counts from the research
- 800-1200 words total
- PLAIN TEXT — no markdown bold (**) or italic (*)
- Return ONLY the newsletter text"""


async def run():
    logger.info("=== Generating AlphaSignal-style Newsletter ===")

    search = YouSearchClient()
    llm = LLMClient()

    try:
        # 1. Research: news, repos, and signals
        logger.info("Researching news...")
        news_responses = await search.batch_search(NEWS_QUERIES)

        logger.info("Researching GitHub repos...")
        repo_responses = await search.batch_search(REPO_QUERIES)

        logger.info("Researching signals...")
        signal_responses = await search.batch_search(SIGNAL_QUERIES)

        # Build research summaries with URLs
        def format_results(responses):
            items = []
            for resp in responses:
                for r in resp.web_results:
                    text_parts = r.snippets[:2] if r.snippets else [r.description]
                    text = " ".join(s.strip()[:200] for s in text_parts if s)
                    if text:
                        items.append(f"[{r.title[:80]}]\nURL: {r.url}\n{text}")
            return "\n\n".join(items[:15])

        news_data = format_results(news_responses)
        github_data = format_results(repo_responses)
        signal_data = format_results(signal_responses)

        research = f"=== NEWS ===\n{news_data}\n\n=== SIGNALS ===\n{signal_data}"
        logger.info("Research collected: news=%d, repos=%d, signals=%d",
                     len(news_data), len(github_data), len(signal_data))

        # 2. Generate newsletter via LLM
        logger.info("Generating newsletter...")
        prompt = NEWSLETTER_PROMPT.format(research=research, github_data=github_data)

        response = await llm.generate(prompt, max_tokens=4000, temperature=0.5)
        if response.error:
            logger.error("LLM error: %s", response.error)
            await telegram_bot.send_notification(f"Newsletter generation failed: {response.error}")
            return

        article = response.text.strip()

        # Clean up any markdown
        article = re.sub(r'\*\*(.+?)\*\*', r'\1', article)
        article = re.sub(r'\*(.+?)\*', r'\1', article)

        logger.info("Generated: %d chars", len(article))

        # 3. Send to Telegram
        header = "AI ENGINEERING WEEKLY — Newsletter Draft:\n\n"
        footer = "\n\n---\nPaste above into your LinkedIn newsletter."

        full_msg = header + article + footer

        # Split into multiple messages if too long
        if len(full_msg) > 4000:
            parts = []
            current = header
            for line in article.split("\n"):
                if len(current) + len(line) + 1 > 3900:
                    parts.append(current)
                    current = ""
                current += line + "\n"
            current += footer
            parts.append(current)

            for i, part in enumerate(parts):
                await telegram_bot.send_notification(part)
                logger.info("Sent part %d/%d to Telegram", i + 1, len(parts))
        else:
            await telegram_bot.send_notification(full_msg)

        logger.info("Newsletter sent to Telegram")

        # 4. Send HTML email via Brevo
        from src.email_sender import send_newsletter_email
        email_recipients = os.getenv("NEWSLETTER_RECIPIENTS", "abhi.6127@gmail.com").split(",")
        email_sent = send_newsletter_email(article, email_recipients)
        if email_sent:
            logger.info("Newsletter email sent to %d recipients", len(email_recipients))
        else:
            logger.warning("Newsletter email send failed or skipped")

        # 5. Save to Google Sheets
        try:
            from src.sheets_client import SheetsClient
            sheets = SheetsClient()
            try:
                ws = sheets._spreadsheet.worksheet("Newsletters")
            except Exception:
                ws = sheets._spreadsheet.add_worksheet("Newsletters", rows=100, cols=3)
                ws.update("A1:C1", [["date", "article", "status"]])

            ws.append_row([date.today().isoformat(), article[:50000], "draft"], value_input_option="RAW")
            logger.info("Saved to Newsletters sheet")
        except Exception as e:
            logger.warning("Could not save to Sheets: %s", e)

        logger.info("=== Newsletter Done ===")

    finally:
        await search.close()
        await llm.close()


def main():
    asyncio.run(run())


if __name__ == "__main__":
    main()
