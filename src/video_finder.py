"""Find short screen-recording demo videos for LinkedIn posts. No face-cam talking heads."""

from __future__ import annotations

import logging
import re

from .search_client import YouSearchClient

logger = logging.getLogger(__name__)

# Keywords that indicate short videos
_SHORT_KEYWORDS = {"shorts", "short", "reel", "reels", "60 seconds", "1 minute", "quick", "under 2 min", "tip", "clip"}
# Keywords that indicate long videos (skip these)
_LONG_KEYWORDS = {"full tutorial", "complete guide", "full course", "beginners guide", "complete beginners", "hour", "masterclass"}
# Junk videos that are completely unrelated
_JUNK_KEYWORDS = {"thermostat", "plumbing", "cooking", "recipe", "workout", "fitness", "makeup", "skincare",
                   "landfill", "repair", "citroen", "car fix", "unboxing haul", "asmr", "mukbang",
                   "vlog", "day in my life", "grwm", "get ready"}

# Face-cam / talking head indicators — penalize these heavily
_FACECAM_KEYWORDS = {"reaction", "my thoughts", "my opinion", "i think", "rant", "hot take",
                      "showdown", "face reveal", "storytime", "podcast", "interview",
                      "controversial", "unpopular opinion", "why i hate", "why i love"}

# Screen recording / demo indicators — boost these
_SCREENCAST_KEYWORDS = {"demo", "screencast", "screen recording", "walkthrough", "tutorial",
                         "how to use", "setup", "getting started", "coding", "live coding",
                         "build", "terminal", "vscode", "ide", "command line", "cli"}


def _extract_theme_keywords(theme: str) -> set[str]:
    """Extract meaningful keywords from theme for relevance matching."""
    stopwords = {"the", "a", "an", "is", "are", "was", "were", "and", "or", "but", "for", "with",
                 "this", "that", "from", "how", "why", "what", "here", "here's", "i", "my",
                 "tested", "built", "using", "via", "its", "it", "in", "on", "to", "of", "by",
                 "same", "both", "task", "stars"}
    words = re.split(r'[\s\-:,/]+', theme.lower())
    keywords = {w.strip("'\"()[]") for w in words if len(w) > 2 and w not in stopwords}
    return keywords


def _relevance_score(title: str, theme_keywords: set[str]) -> int:
    """Score how relevant a video title is to the theme. 0 = no match."""
    title_lower = title.lower()

    # Reject junk videos immediately
    if any(junk in title_lower for junk in _JUNK_KEYWORDS):
        return -100

    score = 0
    title_words = set(re.split(r'[\s\-:,/]+', title_lower))

    # Count keyword matches
    matches = theme_keywords & title_words
    score += len(matches) * 15

    # Partial matches (keyword appears in title but not as exact word)
    for kw in theme_keywords:
        if kw in title_lower and kw not in title_words:
            score += 8

    # Boost AI/tech relevance
    tech_keywords = {"ai", "llm", "model", "agent", "code", "coding", "dev", "developer",
                     "github", "open source", "benchmark", "inference", "gpu", "local",
                     "claude", "gpt", "gemini", "deepseek", "cursor", "copilot", "mcp",
                     "rag", "vector", "embedding", "fine-tune", "api", "framework",
                     "rust", "python", "javascript", "typescript"}
    tech_matches = tech_keywords & title_words
    score += len(tech_matches) * 5

    # PENALIZE face-cam / talking head videos
    for kw in _FACECAM_KEYWORDS:
        if kw in title_lower:
            score -= 40

    # BOOST screen recording / demo style videos
    for kw in _SCREENCAST_KEYWORDS:
        if kw in title_lower:
            score += 25

    return score


def _score_video(url: str, title: str, theme_keywords: set[str]) -> int:
    """Score a video result. Higher = better. Factors: format + relevance + style."""
    url_lower = url.lower()
    title_lower = title.lower()

    # Skip search/listing/playlist pages
    if any(x in url_lower for x in ["/search/", "/search?", "/playlist?", "/channel/", "/@"]):
        return -1

    # Check relevance first — reject irrelevant videos
    relevance = _relevance_score(title, theme_keywords)
    if relevance < 10:
        return -1

    score = relevance

    # YouTube Shorts get format bonus
    if "/shorts/" in url_lower:
        score += 50

    # Regular YouTube video
    elif "youtube.com/watch" in url_lower or "youtu.be" in url_lower:
        score += 10

    # Boost short video indicators in title
    if any(kw in title_lower for kw in _SHORT_KEYWORDS):
        score += 20

    # Penalize long video indicators in title
    if any(kw in title_lower for kw in _LONG_KEYWORDS):
        score -= 30

    return score


def _check_github_readme_media(theme: str) -> dict | None:
    """Check if theme mentions a GitHub repo and extract demo GIF/video from its README."""
    import subprocess

    # Extract repo name like "owner/repo" from theme
    repo_match = re.search(r'([a-zA-Z0-9_.-]+/[a-zA-Z0-9_.-]+)', theme)
    if not repo_match:
        return None

    repo = repo_match.group(1)
    logger.info("Checking GitHub README for demo media: %s", repo)

    try:
        result = subprocess.run(
            ["gh", "api", f"repos/{repo}/readme", "--jq", ".content"],
            capture_output=True, text=True, timeout=10
        )
        if result.returncode != 0 or not result.stdout.strip():
            return None

        import base64
        readme = base64.b64decode(result.stdout.strip()).decode("utf-8", errors="ignore")

        # Look for demo GIFs/videos (priority order)
        media_patterns = [
            # GitHub user-attachments (uploaded GIFs/videos)
            r'https://github\.com/user-attachments/assets/[a-f0-9-]+',
            # Raw GitHub GIFs
            r'https://raw\.githubusercontent\.com/[^\s\)\">\]]+\.gif',
            # Relative GIF/MP4 paths (./demo.gif, assets/demo.gif, etc)
            r'(?:\./|assets/|docs/|images/|img/)?[a-zA-Z0-9_-]+\.(?:gif|mp4)',
        ]

        for pattern in media_patterns:
            matches = re.findall(pattern, readme)
            if matches:
                url = matches[0]
                # Make relative paths absolute
                if not url.startswith("http"):
                    url = f"https://raw.githubusercontent.com/{repo}/main/{url}"
                logger.info("Found GitHub demo media: %s", url[:80])
                return {
                    "url": url,
                    "title": f"{repo} demo",
                    "source": "GitHub",
                    "type": "github_gif",
                }
    except Exception as e:
        logger.warning("GitHub README media check failed: %s", e)

    return None


async def find_video_for_theme(
    theme: str,
    search_client: YouSearchClient,
) -> dict | None:
    """Find demo media for a post. Priority: GitHub README GIF > YouTube screen recording.

    Returns {"url": str, "title": str, "source": str, "type": str} or None.
    """
    # PRIORITY 1: Check GitHub repo README for demo GIF/video (always relevant, no face)
    github_media = _check_github_readme_media(theme)
    if github_media:
        return github_media

    theme_keywords = _extract_theme_keywords(theme)
    logger.info("No GitHub demo found, searching YouTube for screen recording: %s (keywords: %s)", theme[:50], ", ".join(list(theme_keywords)[:6]))

    # Extract tool name for targeted search
    short_theme = theme.split("-")[0].strip()[:40]
    tool_name = theme.split(":")[0].strip()[:30] if ":" in theme else short_theme

    # Search strategies — prioritize screen recordings and demos
    queries = [
        f'site:youtube.com/shorts {tool_name} demo screencast 2026',
        f'site:youtube.com/shorts {tool_name} coding tutorial 2026',
        f'site:youtube.com/shorts {short_theme} screen recording 2026',
        f'site:youtube.com {tool_name} demo walkthrough short 2026',
        f'site:youtube.com {short_theme} how to use demo 2026',
    ]

    results = await search_client.batch_search(queries, count=8)

    candidates = []
    for resp in results:
        for r in resp.web_results:
            score = _score_video(r.url, r.title, theme_keywords)
            if score > 0:
                vtype = "youtube_short" if "/shorts/" in r.url.lower() else "youtube"
                candidates.append({
                    "url": r.url,
                    "title": r.title.strip()[:100],
                    "source": "YouTube",
                    "type": vtype,
                    "score": score,
                })
                logger.info("  candidate: score=%d, %s", score, r.title[:60])

    if not candidates:
        logger.info("No relevant screen recording found for: %s", theme[:50])
        return None

    candidates.sort(key=lambda x: x["score"], reverse=True)
    best = candidates[0]

    # Final relevance gate
    if best["score"] < 25:
        logger.info("Best video score too low (%d): %s — skipping", best["score"], best["title"][:50])
        return None

    logger.info("Selected %s (score=%d): %s — %s", best["type"], best["score"], best["title"][:50], best["url"][:80])
    return {
        "url": best["url"],
        "title": best["title"],
        "source": best["source"],
        "type": best["type"],
    }
