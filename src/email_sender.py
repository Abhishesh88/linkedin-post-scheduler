"""Send HTML newsletter emails via Brevo SMTP."""

from __future__ import annotations

import logging
import os
import re
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

import httpx
from dotenv import load_dotenv

load_dotenv()
logger = logging.getLogger(__name__)

SMTP_HOST = "smtp-relay.brevo.com"
SMTP_PORT = 587
SMTP_LOGIN = os.getenv("BREVO_SMTP_LOGIN", "aa23cb001@smtp-brevo.com")
SMTP_PASSWORD = os.getenv("BREVO_SMTP_KEY", "")
FROM_EMAIL = os.getenv("NEWSLETTER_FROM_EMAIL", "abhishesh.mishra@herovired.com")
FROM_NAME = os.getenv("NEWSLETTER_FROM_NAME", "Abhishesh Mishra")


def _fetch_og_images(content: str) -> dict[str, str]:
    """Extract OG images from URLs found in newsletter content."""
    urls = re.findall(r'https?://[^\s\)\]]+', content)
    og_images = {}

    for url in urls[:12]:
        url = url.rstrip(".,;:")
        try:
            if "github.com/" in url and url.count("/") >= 4:
                repo_path = url.replace("https://github.com/", "").rstrip("/")
                og_images[url] = f"https://opengraph.githubassets.com/1/{repo_path}"
                continue

            resp = httpx.get(url, headers={"User-Agent": "Mozilla/5.0"}, follow_redirects=True, timeout=8)
            if resp.status_code == 200:
                og = re.search(r'property=["\']og:image["\'][^>]+content=["\']([^"\']+)["\']', resp.text)
                if not og:
                    og = re.search(r'content=["\']([^"\']+)["\'][^>]+property=["\']og:image["\']', resp.text)
                if og:
                    og_images[url] = og.group(1)
        except Exception:
            pass

    logger.info("Found %d OG images for newsletter", len(og_images))
    return og_images


def _build_html(content: str, og_images: dict[str, str]) -> str:
    """Convert plain text newsletter to AlphaSignal-style HTML."""

    html = []
    html.append("""<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
</head>
<body style="margin:0; padding:0; background:#f4f4f4; font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,Helvetica,Arial,sans-serif;">

<table width="100%" cellpadding="0" cellspacing="0" style="background:#f4f4f4;">
<tr><td align="center" style="padding:20px 10px;">
<table width="600" cellpadding="0" cellspacing="0" style="background:#ffffff; border-radius:8px; overflow:hidden;">

<!-- Header -->
<tr><td style="background:#111111; padding:30px 40px;">
<h1 style="margin:0; color:#ffffff; font-size:26px; font-weight:700; letter-spacing:-0.5px;">AI Engineering Weekly</h1>
<p style="margin:8px 0 0; color:#999999; font-size:14px;">By Abhishesh Mishra | Associate Director, Engineering</p>
</td></tr>

<!-- Content -->
<tr><td style="padding:30px 40px;">
""")

    lines = content.split("\n")
    in_summary = False
    image_inserted = set()

    for line in lines:
        s = line.strip()

        if s == "SUMMARY":
            html.append('<div style="background:#fafafa; border:1px solid #eee; border-radius:6px; padding:20px; margin:0 0 25px;">')
            html.append('<p style="margin:0 0 8px; font-size:16px; font-weight:700; color:#111;">Summary</p>')
            html.append('<div style="border-top:1px solid #ddd; margin-bottom:12px;"></div>')
            in_summary = True
            continue

        if s == "---":
            if in_summary:
                html.append('</div>')
                in_summary = False
            else:
                html.append('<div style="border-top:1px solid #eee; margin:30px 0;"></div>')
            continue

        if s in ("TOP NEWS", "Top News"):
            html.append('<p style="font-size:18px; font-weight:700; color:#111; margin:25px 0 5px; text-decoration:underline; text-underline-offset:4px;">Top News</p>')
            continue

        if s in ("TOP REPO", "Top Repo"):
            html.append('<p style="font-size:18px; font-weight:700; color:#111; margin:25px 0 5px; text-decoration:underline; text-underline-offset:4px;">Top Repo</p>')
            continue

        if s in ("SIGNALS", "Signals"):
            html.append('<p style="font-size:18px; font-weight:700; color:#111; margin:25px 0 5px; text-decoration:underline; text-underline-offset:4px;">Signals</p>')
            continue

        # Source URL — insert OG image + READ MORE button
        if s.startswith("Source:") or (s.startswith("http") and " " not in s and len(s) > 20):
            url = s.replace("Source: ", "").strip().rstrip(".,;:")
            # Find matching OG image
            for og_url, og_img in og_images.items():
                if og_url == url or url in og_url or og_url in url:
                    if og_url not in image_inserted:
                        html.append(f'<a href="{url}" target="_blank" style="display:block; margin:15px 0;"><img src="{og_img}" style="width:100%; max-width:520px; border-radius:6px; border:1px solid #eee;" alt="Preview"></a>')
                        image_inserted.add(og_url)
                    break
            html.append(f'<table cellpadding="0" cellspacing="0" style="margin:15px 0 25px;"><tr><td style="background:#e74c3c; border-radius:4px; padding:10px 28px;"><a href="{url}" target="_blank" style="color:#ffffff; text-decoration:none; font-weight:600; font-size:14px;">READ MORE</a></td></tr></table>')
            continue

        # Arrow items in summary
        if s.startswith("→ "):
            html.append(f'<p style="margin:6px 0; font-size:14px; color:#333;">→ {s[2:]}</p>')
            continue

        # Numbered signal items
        if s and s[0].isdigit() and ". " in s[:4]:
            num = s.split(".")[0]
            rest = s[len(num)+2:]
            # Make URLs clickable
            url_match = re.search(r'(https?://[^\s\)\]]+)', rest)
            if url_match:
                url = url_match.group(1).rstrip(".,;:")
                rest = rest.replace(url_match.group(1), f'<a href="{url}" style="color:#e74c3c; text-decoration:none;">source</a>')
            html.append(f'<div style="padding:10px 0; border-bottom:1px solid #f0f0f0;"><span style="color:#e74c3c; font-weight:700; font-size:16px;">{num}.</span> <span style="font-size:14px; color:#333;">{rest}</span></div>')
            continue

        if s.startswith("Read time:"):
            html.append(f'<p style="margin:4px 0; font-size:13px; color:#999;">{s}</p>')
            continue

        # Regular paragraph — make URLs clickable, insert OG image if new URL
        if s:
            url_match = re.search(r'(https?://[^\s\)\]]+)', s)
            if url_match:
                url = url_match.group(1).rstrip(".,;:")
                for og_url, og_img in og_images.items():
                    if (og_url == url or url in og_url or og_url in url) and og_url not in image_inserted:
                        html.append(f'<a href="{url}" target="_blank" style="display:block; margin:15px 0;"><img src="{og_img}" style="width:100%; max-width:520px; border-radius:6px; border:1px solid #eee;" alt="Preview"></a>')
                        image_inserted.add(og_url)
                        break
                display_url = url[:50] + "..." if len(url) > 50 else url
                s = s.replace(url_match.group(1), f'<a href="{url}" style="color:#e74c3c; text-decoration:none;">{display_url}</a>')
            html.append(f'<p style="margin:12px 0; font-size:15px; color:#333; line-height:1.65;">{s}</p>')

    html.append("""
<!-- Footer -->
<div style="border-top:1px solid #eee; margin:30px 0 0;"></div>
<p style="font-size:14px; color:#888; text-align:center; margin:20px 0 5px;">Subscribe to <strong>AI Engineering Weekly</strong> on LinkedIn</p>
<p style="font-size:13px; color:#aaa; text-align:center; margin:0;">— Abhishesh Mishra</p>

</td></tr>
</table>
</td></tr>
</table>
</body>
</html>""")

    return "\n".join(html)


def send_newsletter_email(content: str, recipients: list[str], subject: str | None = None) -> bool:
    """Send the newsletter as a formatted HTML email via Brevo."""
    if not SMTP_PASSWORD:
        logger.warning("No BREVO_SMTP_KEY — skipping email send")
        return False

    if not subject:
        # Extract first meaningful line as subject
        for line in content.split("\n"):
            stripped = line.strip()
            if stripped and stripped not in ("SUMMARY", "---", "TOP NEWS", "TOP REPO", "SIGNALS") and not stripped.startswith("Read time"):
                if stripped.startswith("→ "):
                    subject = f"AI Engineering Weekly — {stripped[2:][:60]}"
                    break
        if not subject:
            subject = "AI Engineering Weekly — This Week in AI"

    # Fetch OG images for URLs in content
    og_images = _fetch_og_images(content)

    # Build HTML
    html_content = _build_html(content, og_images)

    # Build email
    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = f"{FROM_NAME} <{FROM_EMAIL}>"
    msg["To"] = ", ".join(recipients)
    msg.attach(MIMEText(content, "plain"))
    msg.attach(MIMEText(html_content, "html"))

    try:
        with smtplib.SMTP(SMTP_HOST, SMTP_PORT) as server:
            server.starttls()
            server.login(SMTP_LOGIN, SMTP_PASSWORD)
            server.sendmail(FROM_EMAIL, recipients, msg.as_string())
        logger.info("Newsletter email sent to %s", ", ".join(recipients))
        return True
    except Exception as e:
        logger.error("Newsletter email failed: %s", e)
        return False
