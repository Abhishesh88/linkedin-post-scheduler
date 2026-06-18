"""Research strategy: deep technical research via You.com for Avi Chawla-style engineering posts."""

from __future__ import annotations

import logging
import random
from datetime import datetime

from .search_client import YouSearchClient, SearchResponse
from .trends_client import get_trending_ai_topics, format_trends_for_prompt
from .utils import current_year

logger = logging.getLogger(__name__)

AI_CATEGORIES = {"ai tools", "ai agents", "developer productivity", "system design", "llm"}

# === DISCOVERY QUERIES ===
# Organized by content type for better topic discovery

_TRENDING_REPOS = [
    "github trending AI repositories this week {year}",
    "github most starred new repos this week {year}",
    "github trending machine learning open source {year}",
    "github trending AI agents framework {year}",
    "new github repo stars exploding this week {year}",
    "site:github.com AI tool stars trending {year}",
]

_BREAKING_NEWS = [
    "AI engineering news this week {year}",
    "Claude Anthropic new feature release {year}",
    "OpenAI announcement this week {year}",
    "DeepSeek new model release {year}",
    "Google Gemini update this week {year}",
    "AI coding agent launch this week {year}",
    "open source AI model released this week {year}",
    "AI startup funding launch this week {year}",
    "MCP server new release this week {year}",
]

_ARCHITECTURE_DEEP_DIVES = [
    "AI agent memory architecture comparison {year}",
    "RAG vs agentic RAG benchmark results {year}",
    "LLM inference optimization technique new {year}",
    "AI agent framework architecture comparison {year}",
    "prompt caching engineering production {year}",
    "MoE mixture of experts routing explained {year}",
    "context engineering LLM best practices {year}",
    "AI agent tool use function calling benchmark {year}",
    "vector database comparison benchmark {year}",
    "LLM evaluation harness benchmark new {year}",
]

_BENCHMARKS_COMPARISONS = [
    "Claude vs GPT vs Gemini benchmark comparison {year}",
    "AI coding agent comparison benchmark {year}",
    "Cursor vs Claude Code vs Copilot benchmark {year}",
    "LLM leaderboard new results this week {year}",
    "AI model speed latency benchmark {year}",
    "local LLM inference benchmark Mac {year}",
    "AI code generation accuracy benchmark {year}",
]

_HACKER_NEWS_VIRAL = [
    "site:news.ycombinator.com AI tool trending {year}",
    "site:news.ycombinator.com LLM local inference {year}",
    "site:news.ycombinator.com AI agent framework {year}",
]

# Leadership / team-impact angles — the intersection niche (technical depth + EM lens)
_LEADERSHIP_ANGLES = [
    "how AI coding agents change engineering team workflow {year}",
    "engineering manager AI adoption productivity impact {year}",
    "AI code review process change engineering teams {year}",
    "hiring engineers in the AI era what changed {year}",
    "developer productivity AI tools real results team {year}",
    "engineering leadership AI agents build vs buy {year}",
    "what junior engineers do now AI automation {year}",
]

# All discovery queries combined for sampling
_ALL_DISCOVERY_QUERIES = (
    _TRENDING_REPOS + _BREAKING_NEWS + _ARCHITECTURE_DEEP_DIVES
    + _BENCHMARKS_COMPARISONS + _HACKER_NEWS_VIRAL + _LEADERSHIP_ANGLES
)

TOPIC_PICKER_PROMPT = """You are picking a topic for a LinkedIn post by Abhishesh Mishra (Associate Director of Engineering).

The post style is like Avi Chawla's "Daily Dose of Data Science" — deep technical analysis with specific numbers.

Abhishesh sits at a rare intersection: deep technical credibility AND real engineering-leadership experience. The BEST topic is one he can analyze technically (specific numbers) AND frame through a leader's lens ("what this means for how teams hire, ship, review code, or decide"). Favor topics with that dual angle.

PRIORITY ORDER (pick the FIRST category that has a good topic):

1. GITHUB TRENDING REPO (HIGHEST PRIORITY) — a repo from the GITHUB TRENDING list below that gained 1000+ stars in the last week, that ALSO has a clear "what this means for engineering teams" angle. These are VERIFIED real repos with real star counts. Pick from this list first.

2. BREAKING AI NEWS — a new model release, tool launch, or benchmark result from THIS WEEK with a team/leadership implication

3. ENGINEERING-LEADERSHIP-IN-THE-AI-ERA — how AI changes code review, hiring, team velocity, build-vs-buy, what juniors do now (use the leadership research below)

4. ARCHITECTURE CONCEPT — agent memory, RAG patterns, MoE routing, prompt caching — only if no good trending repo or news

GITHUB TRENDING (REAL DATA from GitHub API — these repos were created in the last 7 days):
{github_trending}

RESEARCH (from web search this week):
{research}

GOOGLE TRENDS:
{trends}

RECENTLY POSTED TOPICS (AVOID these):
{recent_topics}

RULES:
- STRONGLY PREFER repos from the GITHUB TRENDING section — they have verified star counts
- The topic must be AI/ML/developer tools related
- Must be specific: "antirez/ds4: local DeepSeek V4 inference engine" NOT "local inference tools"
- Include the star count if available: "mattpocock/skills (75K stars): Claude Code skills repo"
- The topic should make an engineer think "I need to try this right now"
- NEVER repeat a topic from the recently posted list
- Skip utility repos (rankings, awesome lists, dotfiles) — pick repos that DO something

Return ONLY a single line: the specific tool/repo with angle (under 15 words). Nothing else."""


def build_research_queries(theme: str, category: str = "") -> list[str]:
    """Generate deep research queries for a theme — optimized for engineering analysis content."""
    year = current_year()
    theme_keyword = theme.split("-")[0].strip()[:50]
    is_ai = (category or "").strip().lower() in AI_CATEGORIES

    queries = []

    # 1. Direct theme research
    queries.append(f'"{theme_keyword}" {year} benchmark results')
    queries.append(f'"{theme_keyword}" vs alternative comparison {year}')

    # 2. GitHub specific — get star counts, creator info
    queries.append(f'site:github.com "{theme_keyword}" stars {year}')
    queries.append(f'"{theme_keyword}" github repo analysis review {year}')

    # 3. Technical deep dive
    queries.append(f'"{theme_keyword}" how it works architecture {year}')
    queries.append(f'"{theme_keyword}" performance benchmark latency {year}')

    # 4. Community discussion
    queries.append(f'site:news.ycombinator.com "{theme_keyword}" {year}')
    queries.append(f'site:reddit.com "{theme_keyword}" review experience {year}')

    if is_ai:
        # 5. AI-specific competitor analysis
        queries.extend([
            f'"{theme_keyword}" vs llama.cpp vs vllm comparison {year}',
            f'AI engineering tools trending this week {year}',
            f'site:linkedin.com "{theme_keyword}" engineer developer {year}',
        ])
    else:
        queries.extend([
            f'"{theme_keyword}" engineering production experience {year}',
            f'"{theme_keyword}" developer review hands-on {year}',
        ])

    return queries


def build_research_summary(research_data: dict, max_chars: int = 4000) -> str:
    """Build condensed research summary organized by type for LLM context."""
    parts = []
    parts.append(f"Sources: {research_data.get('total_sources', 0)} | Snippets: {research_data.get('total_snippets', 0)}")
    parts.append("")

    # Google Trends data
    trends_text = research_data.get("trends", "")
    if trends_text:
        parts.append("== GOOGLE TRENDS ==")
        parts.append(trends_text)
        parts.append("")

    # GitHub trending data
    github_text = research_data.get("github_trending", "")
    if github_text:
        parts.append("== GITHUB TRENDING ==")
        parts.append(github_text)
        parts.append("")

    # Classify snippets
    github_snippets = []
    hacker_news_snippets = []
    benchmark_snippets = []
    linkedin_snippets = []
    news_snippets = []
    general_snippets = []

    benchmark_keywords = {"benchmark", "latency", "tokens/sec", "faster", "accuracy", "performance", "comparison", "vs", "tested"}
    news_keywords = {"launch", "announce", "release", "update", "new feature", "introduces", "debuts", "ships", "open-source"}

    for snippet in research_data.get("all_snippets", []):
        source = snippet.get("source", "").lower()
        text_lower = snippet.get("text", "").lower()

        if "github.com" in source:
            github_snippets.append(snippet)
        elif "news.ycombinator.com" in source or "reddit.com" in source:
            hacker_news_snippets.append(snippet)
        elif "linkedin.com" in source:
            linkedin_snippets.append(snippet)
        elif any(kw in text_lower for kw in benchmark_keywords):
            benchmark_snippets.append(snippet)
        elif any(kw in text_lower for kw in news_keywords):
            news_snippets.append(snippet)
        else:
            general_snippets.append(snippet)

    # Priority order: GitHub > Benchmarks > HN > News > LinkedIn > General
    sections = [
        ("GITHUB DATA", github_snippets, 6),
        ("BENCHMARKS & COMPARISONS", benchmark_snippets, 6),
        ("HACKER NEWS & REDDIT DISCUSSION", hacker_news_snippets, 5),
        ("LATEST NEWS", news_snippets, 5),
        ("LINKEDIN POSTS ON THIS TOPIC", linkedin_snippets, 4),
        ("GENERAL RESEARCH", general_snippets, 5),
    ]

    for title, snippets, limit in sections:
        if snippets:
            parts.append(f"== {title} ==")
            for s in snippets[:limit]:
                parts.append(f"[{s.get('title', '')[:60]}] {s['text'][:300]}")
                parts.append("")

    result = "\n".join(parts)
    if len(result) > max_chars:
        result = result[:max_chars] + "\n... (truncated)"
    return result


def _serialize_results(responses: list[SearchResponse]) -> dict:
    """Convert search responses to serializable dict."""
    data = {
        "timestamp": datetime.now().isoformat(),
        "all_snippets": [],
        "sources": [],
    }
    seen_urls = set()
    for resp in responses:
        for r in resp.web_results:
            if r.url not in seen_urls:
                seen_urls.add(r.url)
                data["sources"].append({"url": r.url, "title": r.title, "description": r.description})
            for snippet in r.snippets:
                if snippet.strip():
                    data["all_snippets"].append({"text": snippet.strip(), "source": r.url, "title": r.title})
        for news in resp.news_results:
            url = news.get("url", "")
            if url and url not in seen_urls:
                seen_urls.add(url)
                data["sources"].append({"url": url, "title": news.get("title", ""), "description": news.get("description", "")})

    data["total_sources"] = len(data["sources"])
    data["total_snippets"] = len(data["all_snippets"])
    return data


def _fetch_github_trending_api() -> str:
    """Fetch actual trending repos from GitHub API — repos created in last 7 days with 500+ stars."""
    import subprocess
    import json
    from datetime import date, timedelta

    week_ago = (date.today() - timedelta(days=7)).isoformat()

    try:
        result = subprocess.run(
            ["gh", "api", "search/repositories",
             "--method", "GET",
             "-f", f"q=created:>{week_ago} stars:>500",
             "-f", "sort=stars",
             "-f", "order=desc",
             "--jq", '.items[:12] | .[] | "\\(.full_name) | \\(.stargazers_count) stars | Created: \\(.created_at[:10]) | \\(.description // "no description" | .[0:100])"'],
            capture_output=True, text=True, timeout=15
        )
        if result.returncode == 0 and result.stdout.strip():
            lines = result.stdout.strip().split("\n")
            logger.info("GitHub API: found %d trending repos from last 7 days", len(lines))
            return "\n".join(f"- {line}" for line in lines)
    except Exception as e:
        logger.warning("GitHub API trending fetch failed: %s", e)

    return ""


async def research_theme(theme: str, search_client: YouSearchClient, category: str = "") -> dict:
    """Research a single theme with deep technical queries."""
    queries = build_research_queries(theme, category=category)
    logger.info("Researching '%s' [%s] with %d queries", theme, category or "no category", len(queries))
    responses = await search_client.batch_search(queries)
    data = _serialize_results(responses)
    data["theme"] = theme

    # Fetch Google Trends for AI topics
    is_ai = (category or "").strip().lower() in AI_CATEGORIES
    if is_ai:
        trends = get_trending_ai_topics()
        data["trends"] = format_trends_for_prompt(trends)
        if trends:
            rising = trends[0].rising_queries[:3]
            if rising:
                logger.info("Searching %d rising Google Trends queries", len(rising))
                rising_responses = await search_client.batch_search(rising)
                rising_data = _serialize_results(rising_responses)
                data["all_snippets"].extend(rising_data["all_snippets"])
                data["sources"].extend(rising_data["sources"])
                data["total_sources"] = len(data["sources"])
                data["total_snippets"] = len(data["all_snippets"])
    else:
        data["trends"] = ""

    logger.info("Research done: '%s' — %d sources, %d snippets", theme, data["total_sources"], data["total_snippets"])
    return data


async def discover_trending_topic(search_client: YouSearchClient, llm_client, recent_themes: list[str]) -> tuple[str, str]:
    """Discover the hottest trending topic using multi-source research."""
    year = current_year()

    # Sample from each category for balanced discovery
    queries = []
    queries += [q.format(year=year) for q in random.sample(_TRENDING_REPOS, min(3, len(_TRENDING_REPOS)))]
    queries += [q.format(year=year) for q in random.sample(_BREAKING_NEWS, min(3, len(_BREAKING_NEWS)))]
    queries += [q.format(year=year) for q in random.sample(_ARCHITECTURE_DEEP_DIVES, min(2, len(_ARCHITECTURE_DEEP_DIVES)))]
    queries += [q.format(year=year) for q in random.sample(_BENCHMARKS_COMPARISONS, min(2, len(_BENCHMARKS_COMPARISONS)))]
    queries += [q.format(year=year) for q in random.sample(_LEADERSHIP_ANGLES, min(2, len(_LEADERSHIP_ANGLES)))]

    logger.info("Discovering trending topics with %d queries...", len(queries))
    responses = await search_client.batch_search(queries)
    data = _serialize_results(responses)

    # Build research summary
    snippets = []
    for s in data["all_snippets"][:50]:
        snippets.append(f"[{s.get('title', '')[:60]}] {s['text'][:300]}")
    research_text = "\n".join(snippets)

    # GitHub trending data — real API call for repos created this week with 500+ stars
    github_text = _fetch_github_trending_api()

    # Google Trends
    trends = get_trending_ai_topics()
    trends_text = format_trends_for_prompt(trends) if trends else "No Google Trends data available."

    # Recent topics to avoid
    recent_text = "\n".join(f"- {t}" for t in recent_themes[:10]) if recent_themes else "None yet."

    # Ask LLM to pick the best topic
    prompt = TOPIC_PICKER_PROMPT.format(
        research=research_text,
        github_trending=github_text,
        trends=trends_text,
        recent_topics=recent_text,
    )

    response = await llm_client.generate(prompt, max_tokens=100, temperature=0.7)
    if response.error or not response.text.strip():
        logger.warning("LLM topic picker failed, using fallback")
        titles = [s.get("title", "") for s in data["all_snippets"] if s.get("title")]
        topic = titles[0] if titles else "AI Coding Agents: Latest Benchmarks and Trends"
    else:
        topic = response.text.strip().strip('"').strip("'")

    logger.info("Discovered trending topic: %s", topic)
    return topic, "ai tools"
