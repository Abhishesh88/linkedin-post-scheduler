"""LinkedIn carousel PDF generator — multi-slide branded posts using Pillow."""

from __future__ import annotations

import logging
import os
import textwrap
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

logger = logging.getLogger(__name__)

OUTPUT_DIR = Path(__file__).parent.parent / "output" / "carousels"

# Brand colors
COLOR_BG = (13, 17, 28)         # deep navy
COLOR_CARD = (22, 28, 45)       # slightly lighter
COLOR_ACCENT = (59, 130, 246)   # blue-500
COLOR_ACCENT2 = (139, 92, 246)  # purple-500
COLOR_WHITE = (255, 255, 255)
COLOR_MUTED = (148, 163, 184)   # slate-400
COLOR_DIM = (71, 85, 105)       # slate-600

# Slide dimensions — portrait 1080x1350
SLIDE_W = 1080
SLIDE_H = 1350
MARGIN = 80

# Bundled Inter font — consistent rendering on all platforms
FONTS_DIR = Path(__file__).parent.parent / "fonts"
FONT_BOLD = FONTS_DIR / "Inter-Bold.ttf"
FONT_REGULAR = FONTS_DIR / "Inter-Regular.ttf"


def _load_font(size: int, bold: bool = False) -> ImageFont.FreeTypeFont:
    font_path = FONT_BOLD if bold else FONT_REGULAR
    if font_path.exists():
        return ImageFont.truetype(str(font_path), size)
    for path in ["/System/Library/Fonts/HelveticaNeue.ttc", "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"]:
        if os.path.exists(path):
            return ImageFont.truetype(path, size)
    return ImageFont.load_default()


def _draw_gradient_bg(img: Image.Image):
    """Draw a subtle gradient background."""
    draw = ImageDraw.Draw(img)
    for y in range(SLIDE_H):
        factor = y / SLIDE_H
        r = int(COLOR_BG[0] + (COLOR_CARD[0] - COLOR_BG[0]) * factor)
        g = int(COLOR_BG[1] + (COLOR_CARD[1] - COLOR_BG[1]) * factor)
        b = int(COLOR_BG[2] + (COLOR_CARD[2] - COLOR_BG[2]) * factor)
        draw.line([(0, y), (SLIDE_W, y)], fill=(r, g, b))


def _draw_accent_bar(draw: ImageDraw.Draw, y: int, width: int = 80):
    """Draw a small accent bar."""
    draw.rectangle([MARGIN, y, MARGIN + width, y + 4], fill=COLOR_ACCENT)


def _draw_slide_number(draw: ImageDraw.Draw, current: int, total: int):
    """Draw slide counter at bottom."""
    font = _load_font(20)
    text = f"{current}/{total}"
    bbox = draw.textbbox((0, 0), text, font=font)
    x = SLIDE_W - MARGIN - (bbox[2] - bbox[0])
    draw.text((x, SLIDE_H - 60), text, fill=COLOR_DIM, font=font)


def _draw_swipe_indicator(draw: ImageDraw.Draw):
    """Draw 'Swipe →' hint on cover slide."""
    font = _load_font(22)
    draw.text((SLIDE_W - MARGIN - 100, SLIDE_H - 60), "Swipe →", fill=COLOR_ACCENT, font=font)


def _wrap_text(text: str, max_chars: int = 30) -> list[str]:
    """Wrap text into lines."""
    return textwrap.wrap(text, width=max_chars)


def create_cover_slide(hook: str, category: str = "", author: str = "Abhishesh Mishra", total_slides: int = 10) -> Image.Image:
    """Create the cover slide (slide 1) with hook text."""
    img = Image.new("RGB", (SLIDE_W, SLIDE_H), COLOR_BG)
    _draw_gradient_bg(img)
    draw = ImageDraw.Draw(img)

    # Category tag
    if category:
        font_cat = _load_font(22)
        cat_text = category.upper()
        bbox = draw.textbbox((0, 0), cat_text, font=font_cat)
        cat_w = bbox[2] - bbox[0]
        draw.rounded_rectangle([MARGIN, 120, MARGIN + cat_w + 30, 120 + 38], radius=6, fill=COLOR_ACCENT)
        draw.text((MARGIN + 15, 124), cat_text, fill=COLOR_WHITE, font=font_cat)

    # Big hook text — centered vertically
    font_hook = _load_font(72, bold=True)
    lines = _wrap_text(hook, max_chars=16)
    total_h = len(lines) * 88
    y = (SLIDE_H - total_h) // 2 - 20
    for line in lines:
        draw.text((MARGIN, y), line, fill=COLOR_WHITE, font=font_hook)
        y += 88

    # Accent bar
    _draw_accent_bar(draw, y + 16, width=120)

    # Bottom branding bar
    draw.rectangle([0, SLIDE_H - 80, SLIDE_W, SLIDE_H], fill=(18, 24, 40))
    font_author = _load_font(28, bold=True)
    font_role = _load_font(24)
    draw.text((MARGIN, SLIDE_H - 68), author, fill=COLOR_WHITE, font=font_author)
    draw.text((400, SLIDE_H - 68), "Associate Director Engineering", fill=COLOR_ACCENT, font=font_role)

    # Swipe indicator
    _draw_swipe_indicator(draw)
    _draw_slide_number(draw, 1, total_slides)

    return img


def create_content_slide(
    number: str,
    title: str,
    body: str,
    slide_num: int,
    total_slides: int,
) -> Image.Image:
    """Create a content slide with a number, title, and body text."""
    img = Image.new("RGB", (SLIDE_W, SLIDE_H), COLOR_BG)
    _draw_gradient_bg(img)
    draw = ImageDraw.Draw(img)

    # Decorative: large faded number in background
    font_bg_num = _load_font(300, bold=True)
    draw.text((SLIDE_W - 350, SLIDE_H - 400), number, fill=(30, 40, 65), font=font_bg_num)

    # Content centered vertically
    font_number = _load_font(80, bold=True)
    font_title = _load_font(56, bold=True)
    font_body = _load_font(36)

    title_lines = _wrap_text(title, max_chars=20)
    body_lines = _wrap_text(body, max_chars=28)

    # Calculate total content height
    content_h = 100 + len(title_lines) * 68 + 30 + len(body_lines) * 48 + 80
    start_y = (SLIDE_H - content_h) // 2

    # Number
    draw.text((MARGIN, start_y), number, fill=COLOR_ACCENT, font=font_number)
    y = start_y + 110

    # Title
    for line in title_lines:
        draw.text((MARGIN, y), line, fill=COLOR_WHITE, font=font_title)
        y += 68

    # Accent bar
    _draw_accent_bar(draw, y + 8, width=100)
    y += 40

    # Body text
    for line in body_lines[:6]:
        draw.text((MARGIN, y), line, fill=COLOR_MUTED, font=font_body)
        y += 48

    # Bottom branding bar
    draw.rectangle([0, SLIDE_H - 50, SLIDE_W, SLIDE_H], fill=(18, 24, 40))
    font_brand = _load_font(18)
    draw.text((MARGIN, SLIDE_H - 38), "Abhishesh Mishra  |  Associate Director Engineering", fill=COLOR_DIM, font=font_brand)

    _draw_slide_number(draw, slide_num, total_slides)

    return img


def create_cta_slide(
    question: str,
    author: str = "Abhishesh Mishra",
    author_title: str = "Associate Director Engineering",
    slide_num: int = 10,
    total_slides: int = 10,
) -> Image.Image:
    """Create the final CTA slide."""
    img = Image.new("RGB", (SLIDE_W, SLIDE_H), COLOR_BG)
    _draw_gradient_bg(img)
    draw = ImageDraw.Draw(img)

    # Decorative: large question mark in background
    font_bg = _load_font(400, bold=True)
    draw.text((SLIDE_W - 350, SLIDE_H - 500), "?", fill=(30, 40, 65), font=font_bg)

    # Question centered
    font_q = _load_font(56, bold=True)
    lines = _wrap_text(question, max_chars=18)
    total_h = len(lines) * 70 + 120
    y = (SLIDE_H - total_h) // 2
    for line in lines:
        draw.text((MARGIN, y), line, fill=COLOR_WHITE, font=font_q)
        y += 70

    # Accent bar
    _draw_accent_bar(draw, y + 16, width=120)

    # Follow CTA
    font_cta = _load_font(32)
    draw.text((MARGIN, y + 50), "Follow for more AI insights", fill=COLOR_ACCENT, font=font_cta)

    # Bottom branding bar
    draw.rectangle([0, SLIDE_H - 80, SLIDE_W, SLIDE_H], fill=(18, 24, 40))
    font_author = _load_font(28, bold=True)
    font_role = _load_font(24)
    draw.text((MARGIN, SLIDE_H - 68), author, fill=COLOR_WHITE, font=font_author)
    draw.text((MARGIN, SLIDE_H - 36), author_title, fill=COLOR_ACCENT, font=font_role)

    _draw_slide_number(draw, slide_num, total_slides)

    return img


def generate_carousel_pdf(
    hook: str,
    points: list[dict],
    cta_question: str,
    category: str = "",
    filename: str | None = None,
) -> str:
    """Generate a LinkedIn carousel PDF.

    Args:
        hook: Cover slide hook text
        points: List of dicts with 'title' and 'body' keys (one per slide)
        cta_question: Final slide question
        category: Category tag for cover slide
        filename: Optional filename

    Returns:
        File path of saved PDF
    """
    total = len(points) + 2  # cover + content slides + CTA

    slides = []

    # Cover slide
    slides.append(create_cover_slide(hook, category=category, total_slides=total))

    # Content slides
    for i, point in enumerate(points):
        slide = create_content_slide(
            number=str(i + 1),
            title=point.get("title", ""),
            body=point.get("body", ""),
            slide_num=i + 2,
            total_slides=total,
        )
        slides.append(slide)

    # CTA slide
    slides.append(create_cta_slide(cta_question, slide_num=total, total_slides=total))

    # Save as PDF
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    if filename is None:
        safe = hook.lower().replace(" ", "-").replace("/", "-")[:40]
        filename = f"{safe}.pdf"

    filepath = OUTPUT_DIR / filename

    # Convert to RGB (PDF requires it)
    cover = slides[0].convert("RGB")
    rest = [s.convert("RGB") for s in slides[1:]]
    cover.save(str(filepath), "PDF", save_all=True, append_images=rest, resolution=150)

    logger.info("Carousel PDF saved: %s (%d slides)", filepath, total)
    return str(filepath)
