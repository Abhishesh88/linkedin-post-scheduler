"""Generate newsletter banner diagrams using Gemma 4 via Gemini API + D2 renderer."""

from __future__ import annotations

import logging
import os
import subprocess
from pathlib import Path

import httpx
from dotenv import load_dotenv

load_dotenv()
logger = logging.getLogger(__name__)

OUTPUT_DIR = Path(__file__).parent.parent / "output" / "diagrams"
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
GEMINI_MODEL = "gemma-4-26b-a4b-it"
GEMINI_URL = f"https://generativelanguage.googleapis.com/v1beta/models/{GEMINI_MODEL}:generateContent"


def generate_d2_code(topic: str) -> str | None:
    """Generate D2 diagram code from a topic using Gemma 4."""
    if not GEMINI_API_KEY:
        logger.warning("No GEMINI_API_KEY — skipping diagram generation")
        return None

    prompt = f"""Generate a D2 diagram for this newsletter topic. The diagram should be a clean architecture/flow diagram.

TOPIC: {topic}

RULES:
- Use D2 syntax (https://d2lang.com)
- Create a flow or architecture diagram showing relationships between concepts
- Max 8-10 nodes
- Use short labels (2-4 words per node)
- Add a title at the top
- Use style attributes for dark theme:
  *.style.fill: "#1a1f35"
  *.style.stroke: "#3b82f6"
  *.style.font-color: "#ffffff"
  *.style.border-radius: 8

Return ONLY the D2 code, nothing else. No markdown fences."""

    payload = {
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {"temperature": 0.5, "maxOutputTokens": 1500},
    }

    try:
        resp = httpx.post(
            f"{GEMINI_URL}?key={GEMINI_API_KEY}",
            json=payload,
            timeout=120,
        )
        if resp.status_code == 200:
            data = resp.json()
            text = data["candidates"][0]["content"]["parts"][0]["text"].strip()
            # Extract D2 code from response — model may include thinking
            import re
            # Try to find D2 code block
            d2_match = re.search(r'```(?:d2)?\s*\n(.*?)```', text, re.DOTALL)
            if d2_match:
                text = d2_match.group(1).strip()
            elif "direction:" in text or "->" in text:
                # Find the D2 code by looking for D2-like patterns
                lines = text.split("\n")
                d2_lines = []
                in_code = False
                for line in lines:
                    stripped = line.strip()
                    if any(kw in stripped for kw in ["direction:", "->", "*.style.", "style.", ": {", "}: "]) or (in_code and stripped and not stripped.startswith("*   ")):
                        in_code = True
                        d2_lines.append(line)
                    elif in_code and not stripped:
                        d2_lines.append("")
                text = "\n".join(d2_lines).strip()
            logger.info("D2 code extracted: %d chars", len(text))
            return text
        else:
            logger.error("Gemma 4 error %d: %s", resp.status_code, resp.text[:200])
            return None
    except Exception as e:
        logger.error("Gemma 4 exception: %s", e)
        return None


def render_d2_to_png(d2_code: str, filename: str = "newsletter_diagram.png") -> str | None:
    """Render D2 code to PNG image using d2 CLI."""
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    d2_path = OUTPUT_DIR / "temp.d2"
    png_path = OUTPUT_DIR / filename

    # Clean up D2 code — strip whitespace and remove unsupported style keywords
    import re
    invalid_styles = {"font-weight", "font-size", "font-family", "text-align", "text-decoration",
                      "background", "margin", "padding", "width", "height", "box-shadow"}
    lines = []
    for line in d2_code.split("\n"):
        stripped = line.strip()
        # Skip lines with invalid D2 style keywords
        if any(f".style.{kw}" in stripped or stripped.startswith(f"{kw}:") for kw in invalid_styles):
            continue
        lines.append(stripped)
    cleaned = "\n".join(lines)
    d2_path.write_text(cleaned)

    try:
        result = subprocess.run(
            ["d2", "--theme", "200", "--pad", "40", str(d2_path), str(png_path)],
            capture_output=True, text=True, timeout=60,
        )
        if result.returncode == 0 and png_path.exists():
            logger.info("Diagram rendered: %s", png_path)
            return str(png_path)
        else:
            logger.error("D2 render failed: %s", result.stderr[:300])
            return None
    except FileNotFoundError:
        logger.warning("d2 not installed — skipping diagram render")
        return None
    except Exception as e:
        logger.error("D2 render exception: %s", e)
        return None


def generate_newsletter_diagram(topic: str, filename: str = "newsletter_diagram.png") -> str | None:
    """Generate a diagram for a newsletter topic. Returns PNG path or None."""
    d2_code = generate_d2_code(topic)
    if not d2_code:
        return None

    return render_d2_to_png(d2_code, filename)
