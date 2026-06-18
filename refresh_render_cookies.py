#!/usr/bin/env python3
"""Login to LinkedIn locally and push cookies to Render via API.

Run this monthly to keep Render's cookies fresh.
Usage: python3 refresh_render_cookies.py
"""
import asyncio
import json
import os
from pathlib import Path

import httpx
from dotenv import load_dotenv

load_dotenv()

RENDER_URL = os.getenv("RENDER_WEBHOOK_URL", "https://linkedin-bot-8pjr.onrender.com")
COOKIES_PATH = Path(__file__).parent / "render_cookies.json"


async def login_and_get_cookies() -> list[dict]:
    """Login to LinkedIn in visible browser, return cookies."""
    from playwright.async_api import async_playwright

    email = os.getenv("LINKEDIN_EMAIL", "")
    password = os.getenv("LINKEDIN_PASSWORD", "")

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=False)
        context = await browser.new_context(viewport={"width": 1280, "height": 800})
        page = await context.new_page()

        print("Opening LinkedIn login...")
        await page.goto("https://www.linkedin.com/login", timeout=60000)
        await page.wait_for_timeout(5000)

        try:
            await page.fill('input#username', email, timeout=10000)
            await page.fill('input#password', password, timeout=10000)
            await page.click('button[type="submit"]', timeout=10000)
        except Exception:
            print("Auto-fill failed. Please login manually in the browser.")

        print("\nLogin in the browser. Handle any CAPTCHA/2FA.")
        print("Once you see your LinkedIn feed, press Enter here...")
        input()

        cookies = await context.cookies()
        await browser.close()
        return cookies


async def push_cookies_to_render(cookies: list[dict]):
    """Push cookies to Render via a POST endpoint."""
    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.post(
            f"{RENDER_URL}/update-cookies",
            json={"cookies": cookies},
        )
        if resp.status_code == 200:
            print(f"Cookies pushed to Render: {resp.text}")
        else:
            print(f"Failed to push: {resp.status_code} {resp.text}")


async def main():
    load_dotenv()

    # 1. Login locally
    cookies = await login_and_get_cookies()
    print(f"Got {len(cookies)} cookies")

    # Save locally
    COOKIES_PATH.write_text(json.dumps(cookies))
    print(f"Saved to {COOKIES_PATH}")

    # 2. Update GitHub secret
    print("\nUpdating GitHub secret...")
    os.system(f'cat {COOKIES_PATH} | gh secret set LINKEDIN_COOKIES --repo Abhishesh88/linkedin-post-scheduler')
    print("GitHub secret updated")

    # 3. Store in Google Sheets (persistent across Render deploys)
    print("\nStoring cookies in Google Sheets...")
    try:
        import sys
        sys.path.insert(0, os.path.dirname(__file__))
        from src.sheets_client import SheetsClient
        sheets = SheetsClient()
        try:
            ws = sheets._spreadsheet.worksheet("CookieStore")
        except Exception:
            ws = sheets._spreadsheet.add_worksheet("CookieStore", rows=2, cols=1)
        ws.update_acell("A1", json.dumps(cookies))
        print(f"Stored {len(cookies)} cookies in CookieStore sheet")
    except Exception as e:
        print(f"Failed to store in Sheets: {e}")

    # 4. Push to Render
    print("\nPushing cookies to Render...")
    await push_cookies_to_render(cookies)


if __name__ == "__main__":
    asyncio.run(main())
