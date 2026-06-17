"""Discovery Engine v2: find trending AI repos with star velocity scoring, spam filtering, and media detection."""

from __future__ import annotations

import base64
import json
import logging
import os
import re
import subprocess
from datetime import date, timedelta

import httpx

logger = logging.getLogger(__name__)

# === SPAM FILTER ===
_SPAM_NAME_KEYWORDS = {
    "hack", "cheat", "crack", "exploit", "mod-menu", "executor", "bypass",
    "free-robux", "fortnite", "roblox", "minecraft", "autoclicker",
    "blooket", "prodigy", "delta-exec", "voidstrap", "jenny-mod",
    "tomodachi", "bongocat", "bongo-cat", "hentai", "subnautica",
    "manager2026", "gopay", "idm", "cs2-external", "overlay-cheat",
}

_SPAM_TOPIC_KEYWORDS = {"game-hacking", "cheat-engine", "game-mod", "roblox-scripts"}

_AI_KEYWORDS = {
    "ai", "llm", "agent", "model", "inference", "coding", "ml", "gpt", "claude",
    "deep", "neural", "transformer", "rag", "vector", "prompt", "mcp", "openai",
    "anthropic", "gemini", "deepseek", "langchain", "embedding", "fine-tune",
    "diffusion", "3d", "generation", "benchmark", "developer", "tool", "skill",
    "terminal", "ide", "code", "copilot", "cursor", "vscode", "framework",
    "typescript", "python", "rust", "workflow", "automation", "pipeline",
}


def _is_spam(name: str, desc: str, topics: list[str] | None = None) -> bool:
    """Filter out game hacks, exploits, non-tech repos, and download managers."""
    lower = f"{name} {desc}".lower()
    if any(kw in lower for kw in _SPAM_NAME_KEYWORDS):
        return True
    if topics and any(t.lower() in _SPAM_TOPIC_KEYWORDS for t in topics):
        return True
    # Filter download managers, game mods, stream overlays
    spam_desc = {"free download", "mod menu", "game hack", "auto clicker", "stream overlay",
                 "virtual companion", "qr codes", "mii community", "browser integration, chrome extension, firefox addon"}
    if any(kw in lower for kw in spam_desc):
        return True
    return False


def _is_ai_relevant(name: str, desc: str, lang: str = "", topics: list[str] | None = None) -> bool:
    """Check if repo is AI/developer tools related."""
    text = f"{name} {desc} {lang} {' '.join(topics or [])}".lower()
    return any(kw in text for kw in _AI_KEYWORDS)


def _star_velocity(stars: int, created: str) -> float:
    """Stars per day since creation."""
    try:
        created_date = date.fromisoformat(created[:10])
        days = max((date.today() - created_date).days, 1)
        return stars / days
    except (ValueError, TypeError):
        return 0.0


# === MEDIA DETECTION ===

def check_repo_media(repo: str) -> dict | None:
    """Check GitHub repo README for demo GIF/video/screenshot. Returns media info or None."""
    try:
        result = subprocess.run(
            ["gh", "api", f"repos/{repo}/readme", "--jq", ".content"],
            capture_output=True, text=True, timeout=10
        )
        if result.returncode != 0:
            return None

        readme = base64.b64decode(result.stdout.strip()).decode("utf-8", errors="ignore")

        # Priority 1: GitHub user-attachments (uploaded GIFs/videos)
        attachments = re.findall(r'https://github\.com/user-attachments/assets/[a-f0-9-]+', readme)
        if attachments:
            return {"url": attachments[0], "type": "attachment", "bonus": 3}

        # Priority 2: Raw GIF/MP4 URLs
        raw_media = re.findall(r'https://raw\.githubusercontent\.com/[^\s\)\">\]]+\.(?:gif|mp4)', readme)
        if raw_media:
            return {"url": raw_media[0], "type": "gif" if ".gif" in raw_media[0] else "mp4", "bonus": 3}

        # Priority 3: Relative GIF/MP4 paths
        relative_media = re.findall(r'(?:\./|assets/|docs/|images/|img/)?[a-zA-Z0-9_-]+\.(?:gif|mp4)', readme)
        if relative_media:
            url = f"https://raw.githubusercontent.com/{repo}/main/{relative_media[0]}"
            return {"url": url, "type": "gif", "bonus": 3}

        # Priority 4: Architecture/diagram SVG
        svgs = re.findall(r'(?:\./|assets/|docs/)?[a-zA-Z0-9_-]*(?:arch|diagram|overview|flow)[a-zA-Z0-9_-]*\.svg', readme)
        if svgs:
            url = f"https://raw.githubusercontent.com/{repo}/main/{svgs[0]}"
            return {"url": url, "type": "svg", "bonus": 1.5}

        # Priority 5: Any screenshot PNGs
        screenshots = re.findall(r'(?:\./|assets/|docs/|images/|screenshots/)?[a-zA-Z0-9_-]+\.(?:png|jpg|webp)', readme)
        # Filter out badges, logos, icons
        real_screenshots = [s for s in screenshots if not any(x in s.lower() for x in ["badge", "logo", "icon", "shield", "banner"])]
        if real_screenshots:
            url = f"https://raw.githubusercontent.com/{repo}/main/{real_screenshots[0]}"
            return {"url": url, "type": "png", "bonus": 2}

    except Exception as e:
        logger.warning("Media check failed for %s: %s", repo, e)

    return None


def download_media(media_info: dict, repo: str) -> str | None:
    """Download media and convert to LinkedIn-compatible format."""
    url = media_info["url"]
    media_type = media_info["type"]

    logger.info("Downloading %s media: %s", media_type, url[:80])
    try:
        resp = httpx.get(url, follow_redirects=True, timeout=30)
        if resp.status_code != 200:
            logger.warning("Download failed: %d", resp.status_code)
            return None

        content_type = resp.headers.get("content-type", "")
        size_kb = len(resp.content) / 1024

        if size_kb < 5:
            logger.info("File too small (%.1f KB), skipping", size_kb)
            return None

        # Determine actual file type
        if "gif" in content_type or url.endswith(".gif"):
            ext = "gif"
        elif "mp4" in content_type or "video" in content_type or url.endswith(".mp4"):
            ext = "mp4"
        elif "svg" in content_type or url.endswith(".svg"):
            ext = "svg"
        else:
            ext = "png"

        raw_path = f"/tmp/repo_media.{ext}"
        with open(raw_path, "wb") as f:
            f.write(resp.content)

        logger.info("Downloaded: %.1f KB (%s)", size_kb, ext)

        # Convert to LinkedIn format
        if ext == "png" or ext == "jpg" or ext == "webp":
            return raw_path

        if ext == "svg":
            output = "/tmp/linkedin_media.png"
            try:
                subprocess.run(
                    ["qlmanage", "-t", "-s", "1200", "-o", "/tmp/", raw_path],
                    capture_output=True, timeout=15
                )
                svg_png = f"{raw_path}.png"
                if os.path.exists(svg_png):
                    os.rename(svg_png, output)
                    return output
            except Exception:
                pass
            return None

        if ext == "gif":
            mp4_path = "/tmp/linkedin_media.mp4"
            try:
                result = subprocess.run(
                    ["ffmpeg", "-y", "-i", raw_path, "-movflags", "+faststart",
                     "-pix_fmt", "yuv420p", "-vf", "scale=trunc(iw/2)*2:trunc(ih/2)*2",
                     mp4_path],
                    capture_output=True, text=True, timeout=60
                )
                if result.returncode == 0 and os.path.exists(mp4_path):
                    logger.info("Converted GIF to MP4: %.1f KB", os.path.getsize(mp4_path) / 1024)
                    return mp4_path
            except FileNotFoundError:
                pass
            # Fallback: first frame as PNG
            try:
                output = "/tmp/linkedin_media.png"
                subprocess.run(
                    ["ffmpeg", "-y", "-i", raw_path, "-vframes", "1", output],
                    capture_output=True, timeout=15
                )
                if os.path.exists(output):
                    return output
            except Exception:
                pass
            return None

        if ext == "mp4":
            return raw_path

    except Exception as e:
        logger.warning("Download/convert failed: %s", e)

    return None


# === MAIN DISCOVERY ===

async def discover_trending_repo(search_client, recent_themes: list[str]) -> list[dict]:
    """Multi-source discovery with scoring. Returns sorted list of candidates.

    Each candidate: {name, stars, desc, velocity, score, media_info, source}
    """
    year = date.today().year
    week_ago = (date.today() - timedelta(days=7)).isoformat()
    three_days_ago = (date.today() - timedelta(days=3)).isoformat()

    candidates = {}  # name -> candidate dict

    # SOURCE 1: GitHub API — this week's fastest growing
    logger.info("Source 1: GitHub API (this week, 100+ stars)...")
    try:
        result = subprocess.run(
            ["gh", "api", "search/repositories", "--method", "GET",
             "-f", f"q=created:>{week_ago} stars:>100",
             "-f", "sort=stars", "-f", "order=desc",
             "--jq", '.items[:25] | .[] | @json'],
            capture_output=True, text=True, timeout=15
        )
        if result.returncode == 0:
            for line in result.stdout.strip().split("\n"):
                if not line.strip():
                    continue
                try:
                    r = json.loads(line)
                    name = r["full_name"]
                    desc = r.get("description") or ""
                    stars = r.get("stargazers_count", 0)
                    created = r.get("created_at", "")[:10]
                    lang = r.get("language") or ""
                    topics = r.get("topics") or []

                    if _is_spam(name, desc, topics):
                        continue
                    if not _is_ai_relevant(name, desc, lang, topics):
                        continue

                    vel = _star_velocity(stars, created)
                    candidates[name] = {
                        "name": name, "stars": stars, "desc": desc[:100],
                        "created": created, "velocity": vel, "lang": lang,
                        "source": "github_api",
                    }
                except (json.JSONDecodeError, KeyError):
                    pass
        logger.info("GitHub API: %d AI repos after filtering", len(candidates))
    except Exception as e:
        logger.warning("GitHub API failed: %s", e)

    # SOURCE 2: GitHub API — pre-viral (last 3 days, 30-500 stars)
    logger.info("Source 2: GitHub API (pre-viral, last 3 days)...")
    try:
        result = subprocess.run(
            ["gh", "api", "search/repositories", "--method", "GET",
             "-f", f"q=created:>{three_days_ago} stars:30..500",
             "-f", "sort=stars", "-f", "order=desc",
             "--jq", '.items[:20] | .[] | @json'],
            capture_output=True, text=True, timeout=15
        )
        if result.returncode == 0:
            for line in result.stdout.strip().split("\n"):
                if not line.strip():
                    continue
                try:
                    r = json.loads(line)
                    name = r["full_name"]
                    if name in candidates:
                        continue
                    desc = r.get("description") or ""
                    stars = r.get("stargazers_count", 0)
                    created = r.get("created_at", "")[:10]
                    lang = r.get("language") or ""
                    topics = r.get("topics") or []

                    if _is_spam(name, desc, topics):
                        continue
                    if not _is_ai_relevant(name, desc, lang, topics):
                        continue

                    vel = _star_velocity(stars, created)
                    candidates[name] = {
                        "name": name, "stars": stars, "desc": desc[:100],
                        "created": created, "velocity": vel, "lang": lang,
                        "source": "pre_viral",
                    }
                except (json.JSONDecodeError, KeyError):
                    pass
        logger.info("Pre-viral: %d total candidates now", len(candidates))
    except Exception as e:
        logger.warning("Pre-viral search failed: %s", e)

    # SOURCE 3: You.com — repos being shared on LinkedIn + HackerNews
    logger.info("Source 3: You.com (LinkedIn + HN shares)...")
    web_queries = [
        f"site:linkedin.com github AI tool trending this week {year}",
        f"site:linkedin.com open source AI agent github {year}",
        f"site:news.ycombinator.com AI tool github trending {year}",
        f"github trending AI developer tool this week {year}",
        f"new github repo AI coding agent viral {year}",
    ]
    try:
        responses = await search_client.batch_search(web_queries, count=8)
        web_repos = set()
        for resp in responses:
            for r in resp.web_results:
                text = f"{r.url} {r.title} {r.description} {' '.join(r.snippets)}"
                found = re.findall(r'github\.com/([a-zA-Z0-9_.-]+/[a-zA-Z0-9_.-]+)', text)
                for repo in found:
                    repo = repo.rstrip("/.")
                    if "/" in repo and repo not in candidates:
                        if not any(x in repo.lower() for x in ["issues", "pull", "blob", "tree", "wiki", "topics", "orgs"]):
                            web_repos.add(repo)

        logger.info("You.com: %d new repo URLs found", len(web_repos))

        # Verify each with GitHub API
        for repo_name in list(web_repos)[:10]:
            try:
                result = subprocess.run(
                    ["gh", "api", f"repos/{repo_name}", "--jq", '@json'],
                    capture_output=True, text=True, timeout=5
                )
                if result.returncode == 0:
                    r = json.loads(result.stdout.strip())
                    stars = r.get("stargazers_count", 0)
                    desc = r.get("description") or ""
                    created = r.get("created_at", "")[:10]
                    lang = r.get("language") or ""
                    topics = r.get("topics") or []

                    if stars < 100 or _is_spam(repo_name, desc, topics):
                        continue

                    vel = _star_velocity(stars, created)
                    candidates[repo_name] = {
                        "name": repo_name, "stars": stars, "desc": desc[:100],
                        "created": created, "velocity": vel, "lang": lang,
                        "source": "web_search",
                    }
            except Exception:
                pass
    except Exception as e:
        logger.warning("You.com search failed: %s", e)

    logger.info("Total candidates after all sources: %d", len(candidates))

    # === SCORE ===
    recent_lower = [t.lower().split(":")[0].split("(")[0].strip() for t in recent_themes]

    scored = []
    for c in candidates.values():
        # Skip already posted
        if c["name"].lower() in recent_lower:
            continue

        vel = c["velocity"]
        stars = c["stars"]

        # Base score = velocity (stars/day)
        score = vel * 100

        # Bonus for high absolute stars (social proof)
        if stars > 1000:
            score *= 1.5
        if stars > 5000:
            score *= 2

        # Check media
        media = check_repo_media(c["name"])
        if media:
            c["media_info"] = media
            score *= media["bonus"]
            logger.info("  %s: %d stars, %.0f vel, media=%s, score=%.0f",
                        c["name"], stars, vel, media["type"], score)
        else:
            c["media_info"] = None
            logger.info("  %s: %d stars, %.0f vel, no media, score=%.0f",
                        c["name"], stars, vel, score)

        c["score"] = score
        scored.append(c)

    scored.sort(key=lambda x: x["score"], reverse=True)
    return scored


def pick_best_with_media(candidates: list[dict]) -> tuple[dict, str | None]:
    """Pick best candidate, preferring those with downloadable media.

    Returns (candidate, media_path).
    """
    # First pass: try candidates with media
    for c in candidates[:8]:
        if c.get("media_info"):
            media_path = download_media(c["media_info"], c["name"])
            if media_path:
                logger.info("SELECTED: %s (%d stars, score=%.0f) with media: %s",
                            c["name"], c["stars"], c["score"], media_path)
                return c, media_path

    # Fallback: best candidate with OG image
    if candidates:
        best = candidates[0]
        og_url = f"https://opengraph.githubassets.com/1/{best['name']}"
        try:
            resp = httpx.get(og_url, follow_redirects=True, timeout=10)
            if resp.status_code == 200 and len(resp.content) > 10000:
                path = "/tmp/linkedin_og.png"
                with open(path, "wb") as f:
                    f.write(resp.content)
                logger.info("FALLBACK: %s with OG image", best["name"])
                return best, path
        except Exception:
            pass
        return best, None

    return {}, None
