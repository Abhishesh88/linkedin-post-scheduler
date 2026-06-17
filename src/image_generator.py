"""LinkedIn post image generator — Playwright HTML-to-image infographics."""

from __future__ import annotations

import html
import logging
import os
import tempfile
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont
from dotenv import load_dotenv
import httpx

load_dotenv()
logger = logging.getLogger(__name__)

OUTPUT_DIR = Path(__file__).parent.parent / "output" / "images"

# Brand colors
COLOR_BG_TOP = (10, 15, 30)      # deep navy top
COLOR_BG_BOT = (20, 30, 55)      # slightly lighter bottom
COLOR_ACCENT = (59, 130, 246)    # blue-500
COLOR_WHITE = (255, 255, 255)
COLOR_MUTED = (160, 175, 200)

# Image size — 1200x627 landscape (LinkedIn recommended, full width on desktop)
IMG_WIDTH = 1200
IMG_HEIGHT = 627

# Bundled Inter font — consistent rendering on all platforms
FONTS_DIR = Path(__file__).parent.parent / "fonts"
FONT_BOLD = FONTS_DIR / "Inter-Bold.ttf"
FONT_REGULAR = FONTS_DIR / "Inter-Regular.ttf"


def _load_font(size: int, bold: bool = False) -> ImageFont.FreeTypeFont:
    font_path = FONT_BOLD if bold else FONT_REGULAR
    if font_path.exists():
        return ImageFont.truetype(str(font_path), size)
    # Fallback to system fonts
    for path in ["/System/Library/Fonts/HelveticaNeue.ttc", "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"]:
        if os.path.exists(path):
            return ImageFont.truetype(path, size)
    return ImageFont.load_default()


def _wrap_title(title: str, max_chars: int = 28) -> list[str]:
    words = title.split()
    lines = []
    current = ""
    for word in words:
        test = f"{current} {word}".strip()
        if len(test) <= max_chars:
            current = test
        else:
            if current:
                lines.append(current)
            current = word
    if current:
        lines.append(current)
    return lines[:4]


TEMPLATE_DIR = Path(__file__).parent.parent / "templates"
INFOGRAPHIC_TEMPLATE = TEMPLATE_DIR / "infographic.html"


ACCENT_COLORS = {
    "orange": {"accent": "#e85d26", "tint": "#fef7f4"},
    "blue":   {"accent": "#2563eb", "tint": "#f0f5ff"},
    "purple": {"accent": "#7c3aed", "tint": "#f5f3ff"},
    "teal":   {"accent": "#0d9488", "tint": "#f0fdfa"},
    "red":    {"accent": "#dc2626", "tint": "#fef2f2"},
}


def _build_cards_html(points: list[dict], grid_cols: int) -> str:
    """Build HTML for grid cards. Last odd card spans full width."""
    total = len(points)
    is_odd = total % grid_cols != 0
    cards = []
    for i, pt in enumerate(points, 1):
        tint_class = "card-tinted" if i % 2 == 0 else ""
        # Last card spans full width if odd count
        full_class = "card-full-width" if (is_odd and i == total) else ""
        title = html.escape(pt["title"])
        body = html.escape(pt["body"])
        cards.append(
            f'<div class="card {tint_class} {full_class}">'
            f'  <div class="card-header">'
            f'    <div class="card-number">{i:02d}</div>'
            f'    <div class="card-title">{title}</div>'
            f'  </div>'
            f'  <div class="card-body">{body}</div>'
            f'</div>'
        )
    return "\n".join(cards)


def _build_stats_bar_html(stats: list[dict] | None) -> str:
    """Build the stats bar HTML. Each stat: {number, label}."""
    if not stats:
        return ""
    items = []
    for s in stats[:4]:
        items.append(
            f'<div class="stat-item">'
            f'  <div class="stat-number">{html.escape(str(s["number"]))}</div>'
            f'  <div class="stat-label">{html.escape(s["label"])}</div>'
            f'</div>'
        )
    return f'<div class="stats-bar">{"".join(items)}</div>'


def generate_infographic(
    title: str,
    points: list[dict],
    author_name: str = "Abhishesh Mishra",
    author_title: str = "Associate Director Engineering",
    category: str = "AI & PRODUCTIVITY",
    subtitle: str = "A complete guide",
    highlight_word: str = "",
    branding_text: str = "Follow for more",
    accent: str = "orange",
    stats: list[dict] | None = None,
    filename: str | None = None,
) -> str:
    """Generate a viral-style LinkedIn infographic using Playwright.

    Args:
        title: Main header text.
        points: List of dicts with 'title' and 'body' keys.
        highlight_word: Word in title to color with accent (optional).
        accent: Color theme — orange, blue, purple, teal, red.
        stats: Optional stats bar, list of {number, label} dicts.
    """
    from playwright.sync_api import sync_playwright

    colors = ACCENT_COLORS.get(accent, ACCENT_COLORS["orange"])
    grid_cols = 3 if len(points) >= 6 else 2

    # Build title HTML with optional highlight
    title_escaped = html.escape(title)
    if highlight_word:
        hw = html.escape(highlight_word)
        title_html = title_escaped.replace(hw, f'<span class="highlight">{hw}</span>')
    else:
        title_html = title_escaped

    # Build components
    cards_html = _build_cards_html(points[:12], grid_cols)
    stats_bar_html = _build_stats_bar_html(stats)

    initials = "".join(w[0].upper() for w in author_name.split()[:2])

    template_html = INFOGRAPHIC_TEMPLATE.read_text()
    filled_html = (
        template_html
        .replace("{{category}}", html.escape(category))
        .replace("{{subtitle}}", html.escape(subtitle))
        .replace("{{title_html}}", title_html)
        .replace("{{cards_html}}", cards_html)
        .replace("{{stats_bar_html}}", stats_bar_html)
        .replace("{{author_name}}", html.escape(author_name))
        .replace("{{author_title}}", html.escape(author_title))
        .replace("{{author_initials}}", initials)
        .replace("{{branding_text}}", html.escape(branding_text))
        .replace("{{accent_color}}", colors["accent"])
        .replace("{{tint_color}}", colors["tint"])
        .replace("{{grid_cols}}", str(grid_cols))
    )

    tmp = tempfile.NamedTemporaryFile(suffix=".html", delete=False, mode="w")
    tmp.write(filled_html)
    tmp.close()

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    if filename is None:
        safe = title.lower().replace(" ", "-").replace("/", "-")[:50]
        filename = f"infographic-{safe}.png"
    filepath = OUTPUT_DIR / filename

    try:
        _render_html_to_png(tmp.name, str(filepath))
        logger.info("Infographic saved: %s", filepath)
        return str(filepath)
    finally:
        os.unlink(tmp.name)


def _render_html_to_png(html_path: str, output_path: str):
    """Render HTML file to PNG using Playwright. Works in both sync and async contexts."""
    import subprocess
    import sys

    # Run Playwright in a subprocess to avoid async/sync conflicts
    script = f"""
import sys
from playwright.sync_api import sync_playwright
with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    page = browser.new_page(viewport={{"width": 1200, "height": 800}}, device_scale_factor=2)
    page.goto("file://{html_path}")
    page.wait_for_timeout(2000)
    # Screenshot only the body element to get exact content height
    page.locator("body").screenshot(path="{output_path}", type="png")
    browser.close()
"""
    result = subprocess.run(
        [sys.executable, "-c", script],
        capture_output=True, text=True, timeout=30,
    )
    if result.returncode != 0:
        raise RuntimeError(f"Playwright render failed: {result.stderr}")


def generate_branded_image(
    theme: str,
    author_name: str = "Abhishesh Mishra",
    author_title: str = "Associate Director Engineering",
    category: str = "",
    filename: str | None = None,
    **kwargs,
) -> str:
    """Generate a clean branded LinkedIn post image.

    Dark gradient background, large bold text, accent color.
    No AI-generated backgrounds — clean and readable.
    """
    img = Image.new("RGB", (IMG_WIDTH, IMG_HEIGHT), COLOR_BG_TOP)
    draw = ImageDraw.Draw(img)

    # --- Subtle gradient background ---
    for y in range(IMG_HEIGHT):
        factor = y / IMG_HEIGHT
        r = int(COLOR_BG_TOP[0] + (COLOR_BG_BOT[0] - COLOR_BG_TOP[0]) * factor)
        g = int(COLOR_BG_TOP[1] + (COLOR_BG_BOT[1] - COLOR_BG_TOP[1]) * factor)
        b = int(COLOR_BG_TOP[2] + (COLOR_BG_BOT[2] - COLOR_BG_TOP[2]) * factor)
        draw.line([(0, y), (IMG_WIDTH, y)], fill=(r, g, b))

    # --- Decorative: connected nodes on right side ---
    nodes = [(900, 120), (1000, 200), (950, 300), (1050, 150), (1100, 260), (1060, 350)]
    for i, (nx, ny) in enumerate(nodes):
        radius = 5 + (i * 2)
        draw.ellipse(
            [nx - radius, ny - radius, nx + radius, ny + radius],
            fill=COLOR_ACCENT,
        )
        if i > 0:
            prev = nodes[i - 1]
            draw.line([prev, (nx, ny)], fill=COLOR_ACCENT, width=1)
    # Cross connections
    draw.line([nodes[0], nodes[3]], fill=COLOR_ACCENT, width=1)
    draw.line([nodes[2], nodes[5]], fill=COLOR_ACCENT, width=1)

    # Top-right subtle glow
    draw.ellipse([IMG_WIDTH - 180, -60, IMG_WIDTH + 60, 180], fill=(30, 50, 90))

    margin = 60

    # --- Title (large, bold, centered vertically) ---
    font_title = _load_font(72, bold=True)
    title_lines = _wrap_title(theme, max_chars=22)
    line_height = 84
    total_title_height = len(title_lines) * line_height
    title_y = (IMG_HEIGHT - total_title_height) // 2 - 30

    for i, line in enumerate(title_lines):
        draw.text((margin, title_y + i * line_height), line, fill=COLOR_WHITE, font=font_title)

    # --- Accent bar under title ---
    bar_y = title_y + total_title_height + 16
    draw.rectangle([margin, bar_y, margin + 100, bar_y + 6], fill=COLOR_ACCENT)

    # --- Author info (bottom-left) ---
    font_name = _load_font(32, bold=True)
    font_role = _load_font(26)
    draw.text((margin, IMG_HEIGHT - 100), author_name, fill=COLOR_WHITE, font=font_name)
    draw.text((margin, IMG_HEIGHT - 62), author_title, fill=COLOR_ACCENT, font=font_role)

    # --- Save ---
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    if filename is None:
        safe = theme.lower().replace(" ", "-").replace("/", "-")[:50]
        filename = f"{safe}.png"

    filepath = OUTPUT_DIR / filename
    img.save(str(filepath), "PNG", quality=95)
    logger.info("Branded image saved: %s", filepath)
    return str(filepath)


async def generate_image(
    theme: str,
    post_text: str = "",
    category: str = "",
    filename: str | None = None,
    points: list[dict] | None = None,
    **kwargs,
) -> str | None:
    """Generate a LinkedIn post image. Uses infographic if points provided."""
    try:
        if points:
            path = generate_infographic(
                title=theme,
                points=points,
                category=category or "AI & PRODUCTIVITY",
                filename=filename,
                **kwargs,
            )
        else:
            path = generate_branded_image(
                theme=theme,
                category=category,
                filename=filename,
            )
        return path
    except Exception as e:
        logger.error("Image generation failed: %s", e)
        return None


async def send_image_to_telegram(image_path: str, caption: str = "") -> bool:
    """Send a generated image to Telegram."""
    bot_token = os.getenv("TELEGRAM_BOT_TOKEN", "")
    chat_id = os.getenv("TELEGRAM_CHAT_ID", "")

    if not bot_token or not chat_id:
        logger.error("Telegram credentials not set")
        return False

    url = f"https://api.telegram.org/bot{bot_token}/sendPhoto"

    try:
        async with httpx.AsyncClient(timeout=30) as client:
            with open(image_path, "rb") as f:
                files = {"photo": (os.path.basename(image_path), f, "image/png")}
                data = {"chat_id": chat_id}
                if caption:
                    data["caption"] = caption[:1024]

                resp = await client.post(url, data=data, files=files)

                if resp.status_code == 200:
                    logger.info("Image sent to Telegram")
                    return True
                else:
                    logger.error("Telegram sendPhoto failed: %d", resp.status_code)
                    return False
    except Exception as e:
        logger.error("Telegram sendPhoto exception: %s", e)
        return False
