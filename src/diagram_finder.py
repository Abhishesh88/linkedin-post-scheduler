"""Find architecture/system design diagram images via You.com search + page scraping."""

from __future__ import annotations

import logging
import os
import re
from pathlib import Path

import httpx

from .search_client import YouSearchClient

logger = logging.getLogger(__name__)

OUTPUT_DIR = Path(__file__).parent.parent / "output" / "images"

# Skip images from sites that watermark
_WATERMARK_DOMAINS = {
    "shutterstock.com", "gettyimages.com", "istockphoto.com",
    "dreamstime.com", "123rf.com", "depositphotos.com",
    "alamy.com", "stock.adobe.com", "canstockphoto.com",
}

_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
}


def _is_good_image_url(url: str) -> bool:
    """Check if URL is likely a good diagram image."""
    lower = url.lower()
    # Must be an image extension or image CDN
    if not any(ext in lower for ext in [".png", ".jpg", ".jpeg", ".webp", "image"]):
        return False
    # Skip watermarked stock sites
    for domain in _WATERMARK_DOMAINS:
        if domain in lower:
            return False
    # Skip tiny icons, avatars, logos
    skip_patterns = ["avatar", "logo", "icon", "favicon", "profile", "thumb", "1x1", "pixel", "tracking", "ads"]
    if any(p in lower for p in skip_patterns):
        return False
    return True


def _extract_images_from_html(html: str, base_url: str) -> list[dict]:
    """Extract image URLs from HTML that look like diagrams. Returns scored list."""
    from urllib.parse import urlparse
    images = []
    seen_urls = set()

    diagram_alt_keywords = {"diagram", "architecture", "pipeline", "flow", "system", "design", "overview", "workflow"}

    for match in re.finditer(r'<img[^>]+>', html, re.IGNORECASE):
        tag = match.group(0)
        # Extract src
        src_match = re.search(r'src=["\']([^"\']+)["\']', tag)
        if not src_match:
            continue
        url = src_match.group(1)

        # Make absolute
        if url.startswith("//"):
            url = "https:" + url
        elif url.startswith("/"):
            parsed = urlparse(base_url)
            url = f"{parsed.scheme}://{parsed.netloc}{url}"
        elif not url.startswith("http"):
            continue

        if url in seen_urls or not _is_good_image_url(url):
            continue
        seen_urls.add(url)

        # Score based on alt text and other attributes
        score = 0
        alt = re.search(r'alt=["\']([^"\']*)["\']', tag)
        alt_text = alt.group(1).lower() if alt else ""

        # Boost images with diagram keywords in alt text
        for kw in diagram_alt_keywords:
            if kw in alt_text:
                score += 20

        # Boost images with width/height attributes suggesting large images
        width_match = re.search(r'width=["\']?(\d+)', tag)
        if width_match and int(width_match.group(1)) > 400:
            score += 10

        # Skip social sharing / branding images
        if any(x in url.lower() for x in ["og-image", "social-share", "twitter-card", "opengraph", "brand"]):
            continue

        images.append({"url": url, "alt": alt_text, "score": score})

    # Sort by score descending — diagram-keyword images first
    images.sort(key=lambda x: x["score"], reverse=True)
    return images


async def find_diagram_image(theme: str, search_client: YouSearchClient) -> str | None:
    """Search for a relevant architecture/diagram image. Returns local file path or None."""
    short_theme = theme.split("-")[0].strip()[:40]
    queries = [
        f'{short_theme} architecture diagram',
        f'{short_theme} system design diagram',
    ]

    logger.info("Searching for diagram image: %s", theme[:50])
    results = await search_client.batch_search(queries, count=5)

    # Collect article URLs that likely contain diagrams
    article_urls = []
    for resp in results:
        for r in resp.web_results:
            url = r.url.lower()
            title = r.title.lower()
            # Prefer pages with diagram/architecture in title
            if any(kw in title for kw in ["diagram", "architecture", "system design", "pipeline", "flow"]):
                article_urls.append(r.url)
            elif any(kw in url for kw in ["diagram", "architecture", "design"]):
                article_urls.append(r.url)

    if not article_urls:
        # Fall back to any result
        for resp in results:
            for r in resp.web_results[:3]:
                article_urls.append(r.url)

    logger.info("Found %d article URLs to scrape for diagrams", len(article_urls))

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    output_path = OUTPUT_DIR / "diagram_search.png"

    # Scrape each article for diagram images
    async with httpx.AsyncClient(timeout=10, follow_redirects=True, headers=_HEADERS) as client:
        for page_url in article_urls[:5]:
            try:
                resp = await client.get(page_url)
                if resp.status_code != 200:
                    continue

                images = _extract_images_from_html(resp.text, page_url)
                logger.info("Found %d images on %s (top score: %d)", len(images), page_url[:60], images[0]["score"] if images else 0)

                # Try to download the best scored image (> 50KB)
                for img in images[:10]:
                    try:
                        img_resp = await client.get(img["url"])
                        if img_resp.status_code == 200 and "image" in img_resp.headers.get("content-type", ""):
                            size = len(img_resp.content)
                            if size > 50000:  # > 50KB = likely a real diagram
                                with open(output_path, "wb") as f:
                                    f.write(img_resp.content)
                                logger.info("Downloaded diagram: %.0f KB, alt='%s' from %s", size / 1024, img["alt"][:40], page_url[:60])
                                return str(output_path)
                    except Exception:
                        continue

            except Exception as e:
                logger.warning("Failed to scrape %s: %s", page_url[:60], e)
                continue

    logger.info("No diagram image found")
    return None
