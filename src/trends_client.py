"""Google Trends client — discover trending AI topics via pytrends."""

from __future__ import annotations

import logging
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)

# AI keywords to track on Google Trends
AI_SEED_KEYWORDS = [
    "Claude AI",
    "Kimi AI",
    "Cursor AI",
    "ChatGPT",
    "AI agents",
]


@dataclass
class TrendingTopic:
    keyword: str
    interest: int = 0  # 0-100 relative interest
    related_queries: list[str] = field(default_factory=list)
    rising_queries: list[str] = field(default_factory=list)


def get_trending_ai_topics() -> list[TrendingTopic]:
    """Fetch trending AI topics from Google Trends via pytrends.

    Returns list of TrendingTopic with interest scores and related/rising queries.
    Falls back gracefully if pytrends is unavailable or rate-limited.
    """
    try:
        from pytrends.request import TrendReq
    except ImportError:
        logger.warning("pytrends not installed — skipping Google Trends")
        return []

    try:
        pytrends = TrendReq(hl="en-US", tz=360)

        # Get interest over time for seed keywords (last 7 days)
        pytrends.build_payload(AI_SEED_KEYWORDS, timeframe="now 7-d", geo="", cat=0)
        interest_df = pytrends.interest_over_time()

        topics = []

        if not interest_df.empty:
            # Get average interest per keyword
            for kw in AI_SEED_KEYWORDS:
                if kw in interest_df.columns:
                    avg_interest = int(interest_df[kw].mean())
                    topics.append(TrendingTopic(keyword=kw, interest=avg_interest))

            # Sort by interest — hottest first
            topics.sort(key=lambda t: t.interest, reverse=True)

        # Get related queries for the top keyword
        if topics:
            top_kw = topics[0].keyword
            pytrends.build_payload([top_kw], timeframe="now 7-d")

            related = pytrends.related_queries()
            if top_kw in related:
                top_data = related[top_kw].get("top")
                rising_data = related[top_kw].get("rising")

                if top_data is not None and not top_data.empty:
                    topics[0].related_queries = top_data["query"].tolist()[:10]

                if rising_data is not None and not rising_data.empty:
                    topics[0].rising_queries = rising_data["query"].tolist()[:10]

        logger.info("Google Trends: found %d topics, top=%s (%d)",
                     len(topics),
                     topics[0].keyword if topics else "none",
                     topics[0].interest if topics else 0)
        return topics

    except Exception as e:
        logger.warning("Google Trends failed (rate limit or network): %s", e)
        return []


def format_trends_for_prompt(topics: list[TrendingTopic]) -> str:
    """Format trending topics as context for the LLM prompt."""
    if not topics:
        return ""

    parts = ["== GOOGLE TRENDS — WHAT'S HOT RIGHT NOW =="]

    for t in topics[:5]:
        parts.append(f"- {t.keyword} (interest: {t.interest}/100)")

    top = topics[0]
    if top.rising_queries:
        parts.append(f"\nRising searches for '{top.keyword}':")
        for q in top.rising_queries[:5]:
            parts.append(f"  - {q}")

    if top.related_queries:
        parts.append(f"\nRelated searches:")
        for q in top.related_queries[:5]:
            parts.append(f"  - {q}")

    return "\n".join(parts)
