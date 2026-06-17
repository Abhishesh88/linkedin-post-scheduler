# LinkedIn Post Scheduler Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build an automated LinkedIn post scheduler that researches topics via You.com, generates posts via Qwen3-235B, manages approval via Telegram interactive buttons, and auto-publishes to LinkedIn — all deployed via GitHub Actions.

**Architecture:** Three GitHub Actions workflows (generate, approval-poll, publish) call Python entry points. Core modules: search_client (You.com with key rotation), llm_client (Qwen via HuggingFace), researcher (topic + competitor research), post_generator (generation + dedup), sheets_client (3-tab Google Sheets), telegram_bot (inline keyboard approval), linkedin_publisher (Marketing API v2).

**Tech Stack:** Python 3.12, aiohttp, gspread, google-auth, youdotcom SDK, python-telegram-bot, GitHub Actions

---

## File Map

| File | Responsibility |
|------|---------------|
| `src/__init__.py` | Package init |
| `src/search_client.py` | You.com API with key rotation, async batch search |
| `src/llm_client.py` | Qwen3-235B via HuggingFace router, retry logic, thinking-mode stripping |
| `src/researcher.py` | Build research queries per theme, execute via search_client, summarize results |
| `src/post_generator.py` | Generate LinkedIn posts via llm_client, dedup against prior posts |
| `src/sheets_client.py` | Read/write all 3 Google Sheets tabs (Settings, Theme Bank, Posts) |
| `src/telegram_bot.py` | Send drafts with inline buttons, poll for callbacks, handle approve/reject |
| `src/linkedin_publisher.py` | Post to LinkedIn Marketing API v2, token management |
| `src/utils.py` | Shared helpers: date math, slugify, logging setup |
| `config/prompts/system_prompt.txt` | Qwen system prompt for post generation |
| `config/prompts/post_prompt.txt` | Qwen user prompt template |
| `generate.py` | Entry point: weekly generation pipeline |
| `poll_approvals.py` | Entry point: Telegram callback polling |
| `publish.py` | Entry point: LinkedIn publishing |
| `requirements.txt` | Python dependencies |
| `.env.example` | Template for environment variables |
| `.gitignore` | Git ignore rules |
| `.github/workflows/generate.yml` | Weekly Monday cron workflow |
| `.github/workflows/approval-poll.yml` | Every-15-min polling workflow |
| `.github/workflows/publish.yml` | Weekday publishing workflow |
| `tests/test_search_client.py` | Tests for You.com search client |
| `tests/test_llm_client.py` | Tests for Qwen LLM client |
| `tests/test_researcher.py` | Tests for research query building and summarization |
| `tests/test_post_generator.py` | Tests for post generation and dedup |
| `tests/test_sheets_client.py` | Tests for Google Sheets integration |
| `tests/test_telegram_bot.py` | Tests for Telegram message formatting and callback handling |
| `tests/test_linkedin_publisher.py` | Tests for LinkedIn API posting |
| `tests/test_generate.py` | Integration test for generate pipeline |

---

### Task 1: Project Scaffolding

**Files:**
- Create: `linkedin-post-scheduler/requirements.txt`
- Create: `linkedin-post-scheduler/.env.example`
- Create: `linkedin-post-scheduler/.gitignore`
- Create: `linkedin-post-scheduler/src/__init__.py`
- Create: `linkedin-post-scheduler/src/utils.py`
- Create: `linkedin-post-scheduler/config/prompts/system_prompt.txt`
- Create: `linkedin-post-scheduler/config/prompts/post_prompt.txt`
- Create: `linkedin-post-scheduler/tests/__init__.py`

- [ ] **Step 1: Initialize git repo**

```bash
cd /Users/abhisheshmishra/linkedin-post-scheduler
git init
```

- [ ] **Step 2: Create requirements.txt**

```
httpx>=0.27.0
aiohttp>=3.9.0
pyyaml>=6.0
python-dotenv>=1.0.0
gspread>=6.0.0
google-auth>=2.0.0
youdotcom>=0.6.0
python-telegram-bot>=21.0
pytest>=8.0.0
pytest-asyncio>=0.23.0
```

- [ ] **Step 3: Create .env.example**

```
# You.com API (comma-separated keys for rotation)
YOU_API_KEYS=ydc-sk-xxx,ydc-sk-yyy

# HuggingFace (Qwen3-235B)
HF_API_KEY=hf_xxx
HF_MODEL=Qwen/Qwen3-235B-A22B
HF_API_URL=https://router.huggingface.co/v1/chat/completions

# Google Sheets
GOOGLE_SHEETS_CREDENTIALS={"type":"service_account",...}
GOOGLE_SHEET_ID=your-sheet-id

# Telegram
TELEGRAM_BOT_TOKEN=123456:ABC-DEF
TELEGRAM_CHAT_ID=123456789

# LinkedIn
LINKEDIN_ACCESS_TOKEN=AQV...
LINKEDIN_PERSON_ID=abc123def
```

- [ ] **Step 4: Create .gitignore**

```
__pycache__/
*.pyc
.env
*.egg-info/
dist/
build/
.pytest_cache/
credentials/
```

- [ ] **Step 5: Create src/__init__.py**

```python
"""LinkedIn Post Scheduler — automated post generation and publishing."""
```

- [ ] **Step 6: Create src/utils.py**

```python
"""Shared utilities for LinkedIn Post Scheduler."""

from __future__ import annotations

import logging
import os
from datetime import date, datetime, timedelta


def setup_logging(name: str = "linkedin-scheduler") -> logging.Logger:
    """Configure logging with consistent format."""
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%H:%M:%S",
    )
    return logging.getLogger(name)


def get_week_dates(week_start: date | None = None) -> list[date]:
    """Return Mon-Fri dates for the given week. Defaults to next Monday."""
    if week_start is None:
        today = date.today()
        # Next Monday (or today if Monday)
        days_ahead = (7 - today.weekday()) % 7
        if days_ahead == 0 and today.weekday() != 0:
            days_ahead = 7
        week_start = today + timedelta(days=days_ahead)
        # If today is Monday, use today
        if today.weekday() == 0:
            week_start = today

    return [week_start + timedelta(days=i) for i in range(5)]


def current_year() -> int:
    """Return current year from env or system clock."""
    return int(os.getenv("CURRENT_YEAR", datetime.now().year))
```

- [ ] **Step 7: Create config/prompts/system_prompt.txt**

```
You are a LinkedIn ghostwriter for a Software Engineering Manager. Write posts that:
- Are 80-200 words, formatted for LinkedIn (short paragraphs, line breaks between ideas)
- Use a conversational, expert, first-person voice
- Share real-world lessons from leading engineering teams
- End with a soft question CTA
- Never fabricate statistics — use [placeholder] brackets for unverified data
- Avoid generic advice — be specific and opinionated
- No hashtags unless explicitly provided
- No emojis unless they add meaning (max 2 per post)
```

- [ ] **Step 8: Create config/prompts/post_prompt.txt**

```
Theme: {theme}
Day: {day} ({weekday})

Voice: {voice}
Audience: {audience}
CTA style: {cta_style}
{hashtags_line}

Research context:
{research_summary}

Prior posts this week (avoid overlap in structure and opening):
{prior_posts_this_week}

Last 5 published posts (avoid semantic duplication):
{prior_published}

Generate one LinkedIn post. Return ONLY the post text, nothing else.
```

- [ ] **Step 9: Create tests/__init__.py**

```python
"""Tests for LinkedIn Post Scheduler."""
```

- [ ] **Step 10: Create .env with real keys from content-generator**

Copy You.com and HuggingFace keys from `/Users/abhisheshmishra/Downloads/content-generator/.env`:

```bash
cat > /Users/abhisheshmishra/linkedin-post-scheduler/.env << 'ENVEOF'
YOU_API_KEYS=ydc-sk-xxx,ydc-sk-yyy

HF_API_KEY=hf_xxx
HF_MODEL=Qwen/Qwen3-235B-A22B
HF_API_URL=https://router.huggingface.co/v1/chat/completions

GOOGLE_SHEETS_CREDENTIALS=
GOOGLE_SHEET_ID=

TELEGRAM_BOT_TOKEN=
TELEGRAM_CHAT_ID=

LINKEDIN_ACCESS_TOKEN=
LINKEDIN_PERSON_ID=
ENVEOF
```

- [ ] **Step 11: Install dependencies**

```bash
cd /Users/abhisheshmishra/linkedin-post-scheduler
pip install -r requirements.txt
```

- [ ] **Step 12: Commit scaffolding**

```bash
git add -A
git commit -m "feat: project scaffolding with deps, prompts, and utils"
```

---

### Task 2: You.com Search Client

**Files:**
- Create: `src/search_client.py`
- Create: `tests/test_search_client.py`

Adapted from content-generator's `search_client.py` — same key rotation + async batch pattern.

- [ ] **Step 1: Write failing test for key rotation**

```python
# tests/test_search_client.py
"""Tests for You.com search client."""

import pytest
from unittest.mock import patch

from src.search_client import YouSearchClient, APIKey, KeyStatus


def test_key_loading_from_env():
    """Keys are loaded and parsed from YOU_API_KEYS env var."""
    with patch.dict("os.environ", {"YOU_API_KEYS": "key1,key2,key3"}):
        client = YouSearchClient()
        assert len(client.keys) == 3
        assert client.keys[0].key == "key1"
        assert client.keys[1].status == KeyStatus.HEALTHY


def test_key_rotation_round_robin():
    """Keys rotate in round-robin order."""
    with patch.dict("os.environ", {"YOU_API_KEYS": "a,b,c"}):
        client = YouSearchClient()
        k1 = client._get_next_key()
        k2 = client._get_next_key()
        k3 = client._get_next_key()
        k4 = client._get_next_key()
        assert k1.key == "a"
        assert k2.key == "b"
        assert k3.key == "c"
        assert k4.key == "a"


def test_dead_key_skipped():
    """Dead keys are skipped in rotation."""
    with patch.dict("os.environ", {"YOU_API_KEYS": "a,b,c"}):
        client = YouSearchClient()
        client.keys[0].status = KeyStatus.DEAD
        k1 = client._get_next_key()
        assert k1.key == "b"


def test_no_healthy_keys_returns_none():
    """Returns None when all keys are dead."""
    with patch.dict("os.environ", {"YOU_API_KEYS": "a,b"}):
        client = YouSearchClient()
        client.keys[0].status = KeyStatus.DEAD
        client.keys[1].status = KeyStatus.DEAD
        assert client._get_next_key() is None


def test_search_response_dataclass():
    """SearchResponse dataclass holds expected fields."""
    from src.search_client import SearchResponse
    resp = SearchResponse(query="test", web_results=[], news_results=[], error=None)
    assert resp.query == "test"
    assert resp.web_results == []
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd /Users/abhisheshmishra/linkedin-post-scheduler
python -m pytest tests/test_search_client.py -v
```

Expected: ModuleNotFoundError — `src.search_client` doesn't exist yet.

- [ ] **Step 3: Implement search_client.py**

```python
# src/search_client.py
"""You.com Search API client with key rotation and async batching."""

from __future__ import annotations

import asyncio
import logging
import os
import time
from dataclasses import dataclass
from enum import Enum

from dotenv import load_dotenv
from youdotcom import You

load_dotenv()
logger = logging.getLogger(__name__)


class KeyStatus(Enum):
    HEALTHY = "healthy"
    COOLDOWN = "cooldown"
    DEAD = "dead"


@dataclass
class APIKey:
    key: str
    status: KeyStatus = KeyStatus.HEALTHY
    cooldown_until: float = 0.0
    total_calls: int = 0
    errors: int = 0


@dataclass
class SearchResult:
    url: str
    title: str
    description: str
    snippets: list[str]


@dataclass
class SearchResponse:
    query: str
    web_results: list[SearchResult]
    news_results: list[dict]
    error: str | None = None


class YouSearchClient:
    """You.com Search API with key rotation and health management."""

    def __init__(self, max_concurrent: int = 5, cooldown_seconds: int = 30):
        raw_keys = os.getenv("YOU_API_KEYS", "")
        self.keys = [APIKey(key=k.strip()) for k in raw_keys.split(",") if k.strip()]
        self._key_index = 0
        self.semaphore = asyncio.Semaphore(max_concurrent)
        self.cooldown_seconds = cooldown_seconds
        logger.info("Loaded %d You.com API keys", len(self.keys))

    async def close(self):
        pass

    def _get_next_key(self) -> APIKey | None:
        now = time.time()
        checked = 0
        while checked < len(self.keys):
            key = self.keys[self._key_index]
            self._key_index = (self._key_index + 1) % len(self.keys)
            checked += 1
            if key.status == KeyStatus.DEAD:
                continue
            if key.status == KeyStatus.COOLDOWN:
                if now >= key.cooldown_until:
                    key.status = KeyStatus.HEALTHY
                else:
                    continue
            if key.status == KeyStatus.HEALTHY:
                return key
        return None

    def _blacklist_key(self, key: APIKey):
        key.status = KeyStatus.DEAD
        logger.warning("Blacklisted key: ...%s", key.key[-8:])

    def _cooldown_key(self, key: APIKey):
        key.status = KeyStatus.COOLDOWN
        key.cooldown_until = time.time() + self.cooldown_seconds
        logger.warning("Key on cooldown: ...%s", key.key[-8:])

    def _parse_sdk_response(self, query: str, sdk_res) -> SearchResponse:
        web = []
        news = []
        if sdk_res.results:
            if sdk_res.results.web:
                for r in sdk_res.results.web:
                    web.append(SearchResult(
                        url=getattr(r, "url", "") or "",
                        title=getattr(r, "title", "") or "",
                        description=getattr(r, "description", "") or "",
                        snippets=list(getattr(r, "snippets", []) or []),
                    ))
            if sdk_res.results.news:
                for n in sdk_res.results.news:
                    news.append({
                        "url": getattr(n, "url", "") or "",
                        "title": getattr(n, "title", "") or "",
                        "description": getattr(n, "description", "") or "",
                    })
        return SearchResponse(query=query, web_results=web, news_results=news)

    async def search(
        self,
        query: str,
        count: int = 10,
        country: str = "US",
        freshness: str | None = None,
    ) -> SearchResponse:
        async with self.semaphore:
            key = self._get_next_key()
            if key is None:
                return SearchResponse(query=query, web_results=[], news_results=[], error="No healthy keys")

            try:
                async with You(key.key) as you:
                    kwargs = {"query": query, "count": count}
                    if country:
                        kwargs["country"] = country
                    if freshness:
                        kwargs["freshness"] = freshness
                    sdk_res = await you.search.unified_async(**kwargs)

                key.total_calls += 1
                return self._parse_sdk_response(query, sdk_res)
            except Exception as e:
                error_str = str(e).lower()
                key.errors += 1
                if "403" in error_str or "forbidden" in error_str:
                    self._blacklist_key(key)
                    return await self.search(query, count, country, freshness)
                if "429" in error_str or "rate" in error_str:
                    self._cooldown_key(key)
                    return await self.search(query, count, country, freshness)
                logger.error("Search error for '%s': %s", query[:50], e)
                return SearchResponse(query=query, web_results=[], news_results=[], error=str(e))

    async def batch_search(self, queries: list[str], **kwargs) -> list[SearchResponse]:
        tasks = [self.search(q, **kwargs) for q in queries]
        return await asyncio.gather(*tasks)

    def get_health_summary(self) -> dict:
        return {
            "total": len(self.keys),
            "healthy": sum(1 for k in self.keys if k.status == KeyStatus.HEALTHY),
            "dead": sum(1 for k in self.keys if k.status == KeyStatus.DEAD),
            "cooldown": sum(1 for k in self.keys if k.status == KeyStatus.COOLDOWN),
        }
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
python -m pytest tests/test_search_client.py -v
```

Expected: All 5 tests PASS.

- [ ] **Step 5: Commit**

```bash
git add src/search_client.py tests/test_search_client.py
git commit -m "feat: You.com search client with key rotation"
```

---

### Task 3: Qwen LLM Client

**Files:**
- Create: `src/llm_client.py`
- Create: `tests/test_llm_client.py`

Adapted from content-generator — Qwen3-235B via HuggingFace router with retry and thinking-tag stripping.

- [ ] **Step 1: Write failing test**

```python
# tests/test_llm_client.py
"""Tests for Qwen LLM client."""

import pytest
from src.llm_client import LLMClient


def test_strip_thinking_tags():
    """Thinking tags from Qwen3 are removed."""
    text = "<think>internal reasoning here</think>The actual response."
    assert LLMClient._strip_thinking(text) == "The actual response."


def test_strip_thinking_multiline():
    """Multi-line thinking tags are removed."""
    text = "<think>\nstep 1\nstep 2\n</think>\nClean output."
    assert LLMClient._strip_thinking(text) == "Clean output."


def test_strip_thinking_no_tags():
    """Text without thinking tags passes through unchanged."""
    text = "Just a normal response."
    assert LLMClient._strip_thinking(text) == "Just a normal response."


def test_client_init_loads_env(monkeypatch):
    """Client loads HF config from environment."""
    monkeypatch.setenv("HF_API_KEY", "test-key")
    monkeypatch.setenv("HF_MODEL", "Qwen/Qwen3-235B-A22B")
    monkeypatch.setenv("HF_API_URL", "https://router.huggingface.co/v1/chat/completions")
    client = LLMClient()
    assert client.hf_key == "test-key"
    assert client.hf_model == "Qwen/Qwen3-235B-A22B"
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
python -m pytest tests/test_llm_client.py -v
```

Expected: FAIL — `src.llm_client` doesn't exist.

- [ ] **Step 3: Implement llm_client.py**

```python
# src/llm_client.py
"""Async LLM client for Qwen3-235B via HuggingFace."""

from __future__ import annotations

import asyncio
import logging
import os
import random
import re
import time
from dataclasses import dataclass

import aiohttp
from dotenv import load_dotenv

load_dotenv()
logger = logging.getLogger(__name__)


@dataclass
class LLMResponse:
    text: str
    model: str
    latency: float
    error: str | None = None


class LLMClient:
    """Async Qwen3-235B client via HuggingFace inference router."""

    def __init__(self, max_concurrent: int = 4):
        self.hf_key = os.getenv("HF_API_KEY")
        self.hf_model = os.getenv("HF_MODEL", "Qwen/Qwen3-235B-A22B")
        self.hf_url = os.getenv("HF_API_URL", "https://router.huggingface.co/v1/chat/completions")
        self.semaphore = asyncio.Semaphore(max_concurrent)
        self._session: aiohttp.ClientSession | None = None

    async def _get_session(self) -> aiohttp.ClientSession:
        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession(
                timeout=aiohttp.ClientTimeout(total=300)
            )
        return self._session

    async def close(self):
        if self._session and not self._session.closed:
            await self._session.close()

    @staticmethod
    def _strip_thinking(text: str) -> str:
        """Strip <think>...</think> tags from Qwen3 output."""
        return re.sub(r"<think>.*?</think>", "", text, flags=re.DOTALL).strip()

    async def generate(
        self,
        user_prompt: str,
        system_prompt: str = "",
        temperature: float = 0.5,
        max_tokens: int = 2000,
    ) -> LLMResponse:
        """Call Qwen3-235B with retry logic."""
        async with self.semaphore:
            start = time.time()
            messages = []
            sys_content = system_prompt
            if sys_content and "/no_think" not in sys_content:
                sys_content = sys_content.rstrip() + " /no_think"
            if sys_content:
                messages.append({"role": "system", "content": sys_content})
            messages.append({"role": "user", "content": user_prompt})

            payload = {
                "model": self.hf_model,
                "messages": messages,
                "max_tokens": max_tokens,
                "temperature": temperature,
                "frequency_penalty": 0.3,
                "stream": False,
            }
            headers = {
                "Authorization": f"Bearer {self.hf_key}",
                "Content-Type": "application/json",
            }

            retry_delays = [5, 15, 30, 60]
            session = await self._get_session()

            for attempt in range(len(retry_delays) + 1):
                try:
                    async with session.post(self.hf_url, json=payload, headers=headers) as resp:
                        if resp.status == 200:
                            data = await resp.json()
                            content = data["choices"][0]["message"]["content"] or ""
                            text = self._strip_thinking(content)
                            latency = time.time() - start
                            logger.info("Qwen call: %.1fs, %d chars", latency, len(text))
                            return LLMResponse(text=text, model=self.hf_model, latency=latency)

                        if resp.status in (429, 503) and attempt < len(retry_delays):
                            delay = retry_delays[attempt] + random.uniform(1, 5)
                            logger.warning("Qwen %d, retry in %.1fs (attempt %d)", resp.status, delay, attempt + 1)
                            await asyncio.sleep(delay)
                            continue

                        error_text = await resp.text()
                        logger.error("Qwen error %d: %s", resp.status, error_text[:200])
                        break

                except Exception as e:
                    logger.error("Qwen exception (attempt %d): %s", attempt + 1, e)
                    if attempt < len(retry_delays):
                        await asyncio.sleep(retry_delays[attempt])
                        continue
                    break

            return LLMResponse(
                text="", model=self.hf_model,
                latency=time.time() - start, error="Qwen unavailable after retries",
            )
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
python -m pytest tests/test_llm_client.py -v
```

Expected: All 4 tests PASS.

- [ ] **Step 5: Commit**

```bash
git add src/llm_client.py tests/test_llm_client.py
git commit -m "feat: Qwen3-235B LLM client via HuggingFace router"
```

---

### Task 4: Researcher (Topic + Competitor Research)

**Files:**
- Create: `src/researcher.py`
- Create: `tests/test_researcher.py`

- [ ] **Step 1: Write failing test**

```python
# tests/test_researcher.py
"""Tests for topic and competitor research."""

import pytest
from src.researcher import build_research_queries, build_research_summary


def test_build_queries_returns_4_per_theme():
    """Each theme produces exactly 4 research queries."""
    queries = build_research_queries("AI engineering in production")
    assert len(queries) == 4


def test_build_queries_include_linkedin():
    """At least one query targets LinkedIn for competitor research."""
    queries = build_research_queries("Technical debt")
    linkedin_queries = [q for q in queries if "linkedin.com" in q.lower()]
    assert len(linkedin_queries) >= 1


def test_build_queries_include_year():
    """Queries include the current year for freshness."""
    queries = build_research_queries("System design")
    year_queries = [q for q in queries if "2026" in q]
    assert len(year_queries) >= 1


def test_build_research_summary_truncates():
    """Summary respects max_chars limit."""
    snippets = [{"text": "x" * 500, "source": f"http://example.com/{i}", "title": f"T{i}"} for i in range(20)]
    data = {"total_sources": 20, "total_snippets": 20, "sources": [], "all_snippets": snippets}
    summary = build_research_summary(data, max_chars=1000)
    assert len(summary) <= 1010  # small buffer for truncation message


def test_build_research_summary_empty_data():
    """Empty research data produces minimal summary."""
    data = {"total_sources": 0, "total_snippets": 0, "sources": [], "all_snippets": []}
    summary = build_research_summary(data)
    assert "Sources found: 0" in summary
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
python -m pytest tests/test_researcher.py -v
```

Expected: FAIL — module not found.

- [ ] **Step 3: Implement researcher.py**

```python
# src/researcher.py
"""Research strategy: topic + LinkedIn competitor research via You.com."""

from __future__ import annotations

import logging
from datetime import datetime

from .search_client import YouSearchClient, SearchResponse
from .utils import current_year

logger = logging.getLogger(__name__)


def build_research_queries(theme: str) -> list[str]:
    """Generate 4 research queries per theme: trends, LinkedIn, audience, data."""
    year = current_year()
    return [
        f'"{theme}" software engineering {year} trends insights',
        f'site:linkedin.com "{theme}" engineering manager',
        f'"{theme}" engineering leadership tips strategies',
        f'"{theme}" software engineering statistics data {year}',
    ]


def build_research_summary(research_data: dict, max_chars: int = 3000) -> str:
    """Build condensed text summary for LLM prompt context."""
    parts = []
    parts.append(f"Sources found: {research_data.get('total_sources', 0)}")
    parts.append(f"Data snippets: {research_data.get('total_snippets', 0)}")
    parts.append("")

    linkedin_snippets = []
    general_snippets = []
    for snippet in research_data.get("all_snippets", []):
        source = snippet.get("source", "").lower()
        if "linkedin.com" in source:
            linkedin_snippets.append(snippet)
        else:
            general_snippets.append(snippet)

    if linkedin_snippets:
        parts.append("== TOP LINKEDIN POSTS ON THIS TOPIC ==")
        for s in linkedin_snippets[:5]:
            parts.append(f"[{s.get('title', '')[:60]}] {s['text'][:300]}")
            parts.append("")

    parts.append("== RESEARCH DATA ==")
    for s in general_snippets[:10]:
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


async def research_theme(theme: str, search_client: YouSearchClient) -> dict:
    """Research a single theme. Returns serialized research data."""
    queries = build_research_queries(theme)
    logger.info("Researching '%s' with %d queries", theme, len(queries))
    responses = await search_client.batch_search(queries)
    data = _serialize_results(responses)
    data["theme"] = theme
    logger.info("Research done: '%s' — %d sources, %d snippets", theme, data["total_sources"], data["total_snippets"])
    return data
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
python -m pytest tests/test_researcher.py -v
```

Expected: All 5 tests PASS.

- [ ] **Step 5: Commit**

```bash
git add src/researcher.py tests/test_researcher.py
git commit -m "feat: topic and LinkedIn competitor researcher"
```

---

### Task 5: Google Sheets Client (3-tab integration)

**Files:**
- Create: `src/sheets_client.py`
- Create: `tests/test_sheets_client.py`

- [ ] **Step 1: Write failing test**

```python
# tests/test_sheets_client.py
"""Tests for Google Sheets client — uses mocked gspread."""

import pytest
from unittest.mock import MagicMock, patch

from src.sheets_client import SheetsClient


@pytest.fixture
def mock_sheets():
    """Create a SheetsClient with mocked gspread."""
    with patch("src.sheets_client.gspread") as mock_gs, \
         patch("src.sheets_client.Credentials") as mock_creds:
        mock_creds.from_service_account_info.return_value = MagicMock()
        mock_gc = MagicMock()
        mock_gs.authorize.return_value = mock_gc

        spreadsheet = MagicMock()
        mock_gc.open_by_key.return_value = spreadsheet

        # Settings tab
        settings_ws = MagicMock()
        settings_ws.get_all_values.return_value = [
            ["voice", "audience", "cta_style", "hashtags"],
            ["conversational, expert", "engineering leaders", "soft question", ""],
        ]

        # Theme Bank tab
        themes_ws = MagicMock()
        themes_ws.get_all_values.return_value = [
            ["theme", "category", "active"],
            ["AI engineering", "AI", "TRUE"],
            ["System design", "Technical", "TRUE"],
            ["Burnout", "Wellbeing", "FALSE"],
        ]

        # Posts tab
        posts_ws = MagicMock()
        posts_ws.get_all_values.return_value = [
            ["week_start", "day", "theme", "draft_text", "char_count", "research_summary",
             "status", "suggested_time", "telegram_msg_id", "feedback", "linkedin_post_id", "published_at"],
        ]

        def get_worksheet(name):
            return {"Settings": settings_ws, "Theme Bank": themes_ws, "Posts": posts_ws}[name]

        spreadsheet.worksheet = get_worksheet

        client = SheetsClient.__new__(SheetsClient)
        client._spreadsheet = spreadsheet
        yield client, spreadsheet, settings_ws, themes_ws, posts_ws


def test_get_settings(mock_sheets):
    client, *_ = mock_sheets
    settings = client.get_settings()
    assert settings["voice"] == "conversational, expert"
    assert settings["audience"] == "engineering leaders"
    assert settings["cta_style"] == "soft question"


def test_get_active_themes(mock_sheets):
    client, *_ = mock_sheets
    themes = client.get_active_themes()
    assert len(themes) == 2
    assert themes[0]["theme"] == "AI engineering"
    assert themes[1]["theme"] == "System design"


def test_inactive_themes_excluded(mock_sheets):
    client, *_ = mock_sheets
    themes = client.get_active_themes()
    theme_names = [t["theme"] for t in themes]
    assert "Burnout" not in theme_names


def test_get_prior_posts_empty(mock_sheets):
    client, *_ = mock_sheets
    posts = client.get_prior_posts(limit=5)
    assert posts == []
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
python -m pytest tests/test_sheets_client.py -v
```

Expected: FAIL — module not found.

- [ ] **Step 3: Implement sheets_client.py**

```python
# src/sheets_client.py
"""Google Sheets integration — 3 tabs: Settings, Theme Bank, Posts."""

from __future__ import annotations

import json
import logging
import os

from dotenv import load_dotenv
import gspread
from google.oauth2.service_account import Credentials

load_dotenv()
logger = logging.getLogger(__name__)

SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive.readonly",
]

# Posts tab column indices (1-indexed for gspread)
POST_COL_WEEK_START = 1
POST_COL_DAY = 2
POST_COL_THEME = 3
POST_COL_DRAFT = 4
POST_COL_CHARS = 5
POST_COL_RESEARCH = 6
POST_COL_STATUS = 7
POST_COL_TIME = 8
POST_COL_TELEGRAM_ID = 9
POST_COL_FEEDBACK = 10
POST_COL_LINKEDIN_ID = 11
POST_COL_PUBLISHED_AT = 12


class SheetsClient:
    """Manages the 3-tab LinkedIn Post Scheduler sheet."""

    def __init__(self):
        creds_json = os.getenv("GOOGLE_SHEETS_CREDENTIALS", "")
        creds_file = os.getenv("GOOGLE_SHEETS_CREDENTIALS_FILE", "")
        sheet_id = os.getenv("GOOGLE_SHEET_ID", "")

        if creds_json:
            creds_info = json.loads(creds_json)
            creds = Credentials.from_service_account_info(creds_info, scopes=SCOPES)
        elif creds_file and os.path.exists(creds_file):
            creds = Credentials.from_service_account_file(creds_file, scopes=SCOPES)
        else:
            raise ValueError("No Google Sheets credentials. Set GOOGLE_SHEETS_CREDENTIALS or GOOGLE_SHEETS_CREDENTIALS_FILE")

        gc = gspread.authorize(creds)
        self._spreadsheet = gc.open_by_key(sheet_id)
        logger.info("Connected to Google Sheet: %s", sheet_id)

    def _ws(self, name: str):
        return self._spreadsheet.worksheet(name)

    def get_settings(self) -> dict:
        """Read the Settings tab (single row of config)."""
        ws = self._ws("Settings")
        rows = ws.get_all_values()
        if len(rows) < 2:
            raise ValueError("Settings tab is empty — needs header + 1 data row")
        headers = [h.strip().lower() for h in rows[0]]
        values = rows[1]
        return {headers[i]: values[i].strip() if i < len(values) else "" for i in range(len(headers))}

    def get_active_themes(self) -> list[dict]:
        """Read active themes from Theme Bank tab."""
        ws = self._ws("Theme Bank")
        rows = ws.get_all_values()
        if len(rows) < 2:
            return []
        headers = [h.strip().lower() for h in rows[0]]
        themes = []
        for row in rows[1:]:
            entry = {headers[i]: row[i].strip() if i < len(row) else "" for i in range(len(headers))}
            if entry.get("active", "TRUE").upper() == "TRUE":
                themes.append(entry)
        return themes

    def get_prior_posts(self, limit: int = 5) -> list[dict]:
        """Get last N published posts for deduplication."""
        ws = self._ws("Posts")
        rows = ws.get_all_values()
        if len(rows) < 2:
            return []
        headers = [h.strip().lower() for h in rows[0]]
        published = []
        for row in rows[1:]:
            entry = {headers[i]: row[i].strip() if i < len(row) else "" for i in range(len(headers))}
            if entry.get("status", "").lower() == "published":
                published.append(entry)
        return published[-limit:]

    def get_posts_by_status(self, status: str) -> list[dict]:
        """Get posts with a given status, including their row numbers."""
        ws = self._ws("Posts")
        rows = ws.get_all_values()
        if len(rows) < 2:
            return []
        headers = [h.strip().lower() for h in rows[0]]
        results = []
        for i, row in enumerate(rows[1:], start=2):
            entry = {headers[j]: row[j].strip() if j < len(row) else "" for j in range(len(headers))}
            entry["_row"] = i
            if entry.get("status", "").lower() == status.lower():
                results.append(entry)
        return results

    def append_post(self, post_data: dict):
        """Append a new post row to the Posts tab."""
        ws = self._ws("Posts")
        row = [
            post_data.get("week_start", ""),
            post_data.get("day", ""),
            post_data.get("theme", ""),
            post_data.get("draft_text", ""),
            str(post_data.get("char_count", 0)),
            post_data.get("research_summary", ""),
            post_data.get("status", "pending_approval"),
            post_data.get("suggested_time", "09:00 UTC"),
            str(post_data.get("telegram_msg_id", "")),
            post_data.get("feedback", ""),
            post_data.get("linkedin_post_id", ""),
            post_data.get("published_at", ""),
        ]
        ws.append_row(row, value_input_option="USER_ENTERED")
        logger.info("Appended post for %s: %s", post_data.get("day"), post_data.get("theme"))

    def update_post_status(self, row_number: int, status: str, **extra):
        """Update a post's status and optional extra fields."""
        ws = self._ws("Posts")
        ws.update_cell(row_number, POST_COL_STATUS, status)
        if "telegram_msg_id" in extra:
            ws.update_cell(row_number, POST_COL_TELEGRAM_ID, str(extra["telegram_msg_id"]))
        if "feedback" in extra:
            ws.update_cell(row_number, POST_COL_FEEDBACK, extra["feedback"])
        if "linkedin_post_id" in extra:
            ws.update_cell(row_number, POST_COL_LINKEDIN_ID, extra["linkedin_post_id"])
        if "published_at" in extra:
            ws.update_cell(row_number, POST_COL_PUBLISHED_AT, extra["published_at"])
        logger.info("Row %d status → %s", row_number, status)

    def find_post_row_by_telegram_id(self, telegram_msg_id: int) -> dict | None:
        """Find a post row by its Telegram message ID."""
        ws = self._ws("Posts")
        rows = ws.get_all_values()
        if len(rows) < 2:
            return None
        headers = [h.strip().lower() for h in rows[0]]
        for i, row in enumerate(rows[1:], start=2):
            entry = {headers[j]: row[j].strip() if j < len(row) else "" for j in range(len(headers))}
            entry["_row"] = i
            if entry.get("telegram_msg_id", "") == str(telegram_msg_id):
                return entry
        return None
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
python -m pytest tests/test_sheets_client.py -v
```

Expected: All 4 tests PASS.

- [ ] **Step 5: Commit**

```bash
git add src/sheets_client.py tests/test_sheets_client.py
git commit -m "feat: Google Sheets 3-tab client (Settings, Theme Bank, Posts)"
```

---

### Task 6: Post Generator (generation + deduplication)

**Files:**
- Create: `src/post_generator.py`
- Create: `tests/test_post_generator.py`

- [ ] **Step 1: Write failing test**

```python
# tests/test_post_generator.py
"""Tests for LinkedIn post generation and deduplication."""

import pytest
from src.post_generator import assign_themes_to_days, format_post_prompt, check_char_limits
from datetime import date


def test_assign_themes_5_themes():
    """5 themes → 1 per day, no repeats."""
    themes = ["A", "B", "C", "D", "E"]
    days = [date(2026, 4, 20), date(2026, 4, 21), date(2026, 4, 22), date(2026, 4, 23), date(2026, 4, 24)]
    assigned = assign_themes_to_days(themes, days)
    assert len(assigned) == 5
    assert len(set(t for _, t in assigned)) == 5


def test_assign_themes_fewer_than_5():
    """3 themes cycle but never repeat on consecutive days."""
    themes = ["A", "B", "C"]
    days = [date(2026, 4, 20), date(2026, 4, 21), date(2026, 4, 22), date(2026, 4, 23), date(2026, 4, 24)]
    assigned = assign_themes_to_days(themes, days)
    assert len(assigned) == 5
    for i in range(len(assigned) - 1):
        assert assigned[i][1] != assigned[i + 1][1], "Consecutive days must not repeat theme"


def test_assign_themes_more_than_5():
    """15 themes → only 5 selected, no repeats."""
    themes = [f"theme_{i}" for i in range(15)]
    days = [date(2026, 4, 20 + i) for i in range(5)]
    assigned = assign_themes_to_days(themes, days)
    assert len(assigned) == 5
    assert len(set(t for _, t in assigned)) == 5


def test_format_post_prompt():
    """Prompt template is populated correctly."""
    prompt = format_post_prompt(
        theme="AI engineering",
        day="2026-04-21",
        weekday="Tuesday",
        voice="conversational",
        audience="engineering leaders",
        cta_style="soft question",
        hashtags="",
        research_summary="Some research data here",
        prior_posts_this_week="None yet",
        prior_published="None",
    )
    assert "AI engineering" in prompt
    assert "Tuesday" in prompt
    assert "Some research data here" in prompt


def test_check_char_limits():
    """Posts over 3000 chars flagged, over 1500 warned."""
    short = "x" * 100
    medium = "x" * 1600
    long_post = "x" * 3100

    assert check_char_limits(short) == {"ok": True, "warning": False, "chars": 100}
    assert check_char_limits(medium) == {"ok": True, "warning": True, "chars": 1600}
    assert check_char_limits(long_post) == {"ok": False, "warning": True, "chars": 3100}
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
python -m pytest tests/test_post_generator.py -v
```

Expected: FAIL — module not found.

- [ ] **Step 3: Implement post_generator.py**

```python
# src/post_generator.py
"""LinkedIn post generation with theme assignment and deduplication."""

from __future__ import annotations

import logging
import os
import random
from datetime import date
from pathlib import Path

from .llm_client import LLMClient, LLMResponse

logger = logging.getLogger(__name__)

PROMPTS_DIR = Path(__file__).parent.parent / "config" / "prompts"


def _load_prompt(name: str) -> str:
    path = PROMPTS_DIR / name
    return path.read_text().strip()


def assign_themes_to_days(themes: list[str], days: list[date]) -> list[tuple[date, str]]:
    """Assign one theme per day. Shuffle, cycle if < 5, never repeat consecutive."""
    pool = list(themes)
    random.shuffle(pool)

    assigned = []
    used_index = 0
    last_theme = None

    for day in days:
        # Find a theme that isn't the same as the previous day
        attempts = 0
        while attempts < len(pool):
            candidate = pool[used_index % len(pool)]
            used_index += 1
            attempts += 1
            if candidate != last_theme or len(pool) == 1:
                assigned.append((day, candidate))
                last_theme = candidate
                break
        else:
            # Fallback: just pick the next one
            candidate = pool[used_index % len(pool)]
            used_index += 1
            assigned.append((day, candidate))
            last_theme = candidate

    return assigned


def format_post_prompt(
    theme: str,
    day: str,
    weekday: str,
    voice: str,
    audience: str,
    cta_style: str,
    hashtags: str,
    research_summary: str,
    prior_posts_this_week: str,
    prior_published: str,
) -> str:
    """Format the user prompt for post generation."""
    template = _load_prompt("post_prompt.txt")
    hashtags_line = f"Approved hashtags: {hashtags}" if hashtags else "No hashtags."
    return template.format(
        theme=theme,
        day=day,
        weekday=weekday,
        voice=voice,
        audience=audience,
        cta_style=cta_style,
        hashtags_line=hashtags_line,
        research_summary=research_summary,
        prior_posts_this_week=prior_posts_this_week,
        prior_published=prior_published,
    )


def check_char_limits(text: str) -> dict:
    """Check LinkedIn character limits: warn at 1500, reject at 3000."""
    chars = len(text)
    return {
        "ok": chars <= 3000,
        "warning": chars > 1500,
        "chars": chars,
    }


async def generate_post(
    llm: LLMClient,
    theme: str,
    day: str,
    weekday: str,
    settings: dict,
    research_summary: str,
    prior_posts_this_week: list[str],
    prior_published: list[str],
) -> str:
    """Generate a single LinkedIn post via Qwen3-235B."""
    system_prompt = _load_prompt("system_prompt.txt")
    user_prompt = format_post_prompt(
        theme=theme,
        day=day,
        weekday=weekday,
        voice=settings.get("voice", "conversational, expert, first-person"),
        audience=settings.get("audience", "engineering leaders"),
        cta_style=settings.get("cta_style", "soft question"),
        hashtags=settings.get("hashtags", ""),
        research_summary=research_summary,
        prior_posts_this_week="\n---\n".join(prior_posts_this_week) if prior_posts_this_week else "None yet.",
        prior_published="\n---\n".join(prior_published) if prior_published else "None.",
    )

    response = await llm.generate(user_prompt, system_prompt=system_prompt)
    if response.error:
        logger.error("Post generation failed for %s: %s", theme, response.error)
        return ""

    draft = response.text.strip()

    # Check char limits
    limits = check_char_limits(draft)
    if not limits["ok"]:
        logger.warning("Post for %s exceeds 3000 chars (%d). Truncating.", theme, limits["chars"])
        draft = draft[:3000]
    elif limits["warning"]:
        logger.warning("Post for %s is long: %d chars", theme, limits["chars"])

    return draft


async def check_similarity(llm: LLMClient, draft: str, prior_posts: list[str]) -> bool:
    """Use Qwen to check if draft is >70% semantically similar to any prior post."""
    if not prior_posts:
        return False

    prior_text = "\n---\n".join(prior_posts[:5])
    prompt = f"""Compare this draft LinkedIn post against the prior posts below.
Is the draft >70% semantically similar (same core topic AND similar opening hook) to ANY prior post?
Reply with ONLY "SIMILAR" or "UNIQUE".

DRAFT:
{draft}

PRIOR POSTS:
{prior_text}"""

    response = await llm.generate(prompt, temperature=0.1, max_tokens=50)
    result = response.text.strip().upper()
    is_similar = "SIMILAR" in result
    if is_similar:
        logger.info("Draft flagged as similar to prior post — will regenerate")
    return is_similar
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
python -m pytest tests/test_post_generator.py -v
```

Expected: All 5 tests PASS.

- [ ] **Step 5: Commit**

```bash
git add src/post_generator.py tests/test_post_generator.py
git commit -m "feat: post generator with theme assignment and dedup"
```

---

### Task 7: Telegram Bot (Send drafts + handle callbacks)

**Files:**
- Create: `src/telegram_bot.py`
- Create: `tests/test_telegram_bot.py`

- [ ] **Step 1: Write failing test**

```python
# tests/test_telegram_bot.py
"""Tests for Telegram bot message formatting and callback parsing."""

import pytest
from src.telegram_bot import format_draft_message, parse_callback_data


def test_format_draft_message():
    """Draft message includes theme, text, and char count."""
    msg = format_draft_message(
        day="2026-04-21",
        weekday="Tuesday",
        theme="AI engineering",
        draft_text="This is a test post about AI.",
        char_count=28,
        suggested_time="09:00 UTC",
    )
    assert "Tuesday" in msg
    assert "AI engineering" in msg
    assert "This is a test post about AI." in msg
    assert "28" in msg


def test_parse_callback_approve():
    """Approve callback data is parsed correctly."""
    result = parse_callback_data("approve_5")
    assert result == {"action": "approve", "row": 5}


def test_parse_callback_reject():
    """Reject callback data is parsed correctly."""
    result = parse_callback_data("reject_12")
    assert result == {"action": "reject", "row": 12}


def test_parse_callback_invalid():
    """Invalid callback data returns None."""
    result = parse_callback_data("invalid_data")
    assert result is None
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
python -m pytest tests/test_telegram_bot.py -v
```

Expected: FAIL — module not found.

- [ ] **Step 3: Implement telegram_bot.py**

```python
# src/telegram_bot.py
"""Telegram integration — send drafts with inline buttons, poll for callbacks."""

from __future__ import annotations

import json
import logging
import os

import httpx
from dotenv import load_dotenv

load_dotenv()
logger = logging.getLogger(__name__)


def _bot_token() -> str:
    return os.getenv("TELEGRAM_BOT_TOKEN", "")


def _chat_id() -> str:
    return os.getenv("TELEGRAM_CHAT_ID", "")


def _api_url(method: str) -> str:
    return f"https://api.telegram.org/bot{_bot_token()}/{method}"


def format_draft_message(
    day: str, weekday: str, theme: str, draft_text: str, char_count: int, suggested_time: str,
) -> str:
    """Format a draft post for Telegram display."""
    return (
        f"LinkedIn Draft -- {weekday}, {day}\n"
        f"Theme: {theme}\n\n"
        f"---\n{draft_text}\n---\n\n"
        f"{char_count} chars | Scheduled: {suggested_time}"
    )


def parse_callback_data(data: str) -> dict | None:
    """Parse inline button callback data like 'approve_5' or 'reject_12'."""
    parts = data.split("_", 1)
    if len(parts) != 2 or parts[0] not in ("approve", "reject"):
        return None
    try:
        return {"action": parts[0], "row": int(parts[1])}
    except ValueError:
        return None


async def send_draft(
    day: str, weekday: str, theme: str, draft_text: str, char_count: int,
    suggested_time: str, row_number: int,
) -> int | None:
    """Send a draft post to Telegram with Approve/Reject inline buttons. Returns message_id."""
    text = format_draft_message(day, weekday, theme, draft_text, char_count, suggested_time)

    inline_keyboard = {
        "inline_keyboard": [[
            {"text": "Approve", "callback_data": f"approve_{row_number}"},
            {"text": "Reject", "callback_data": f"reject_{row_number}"},
        ]]
    }

    payload = {
        "chat_id": _chat_id(),
        "text": text,
        "reply_markup": json.dumps(inline_keyboard),
    }

    async with httpx.AsyncClient() as client:
        resp = await client.post(_api_url("sendMessage"), json=payload)
        if resp.status_code == 200:
            data = resp.json()
            msg_id = data["result"]["message_id"]
            logger.info("Sent draft to Telegram: msg_id=%d, row=%d", msg_id, row_number)
            return msg_id
        else:
            logger.error("Telegram sendMessage failed: %d %s", resp.status_code, resp.text[:200])
            return None


async def send_notification(text: str):
    """Send a plain text notification to Telegram."""
    payload = {"chat_id": _chat_id(), "text": text}
    async with httpx.AsyncClient() as client:
        resp = await client.post(_api_url("sendMessage"), json=payload)
        if resp.status_code != 200:
            logger.error("Telegram notification failed: %d", resp.status_code)


async def answer_callback(callback_query_id: str, text: str):
    """Answer a Telegram inline button callback."""
    payload = {"callback_query_id": callback_query_id, "text": text}
    async with httpx.AsyncClient() as client:
        await client.post(_api_url("answerCallbackQuery"), json=payload)


async def get_updates(offset: int = 0) -> list[dict]:
    """Poll for new Telegram updates (callback queries)."""
    payload = {"offset": offset, "timeout": 5, "allowed_updates": ["callback_query"]}
    async with httpx.AsyncClient(timeout=15) as client:
        resp = await client.post(_api_url("getUpdates"), json=payload)
        if resp.status_code == 200:
            return resp.json().get("result", [])
        logger.error("Telegram getUpdates failed: %d", resp.status_code)
        return []
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
python -m pytest tests/test_telegram_bot.py -v
```

Expected: All 4 tests PASS.

- [ ] **Step 5: Commit**

```bash
git add src/telegram_bot.py tests/test_telegram_bot.py
git commit -m "feat: Telegram bot with inline approve/reject buttons"
```

---

### Task 8: LinkedIn Publisher

**Files:**
- Create: `src/linkedin_publisher.py`
- Create: `tests/test_linkedin_publisher.py`

- [ ] **Step 1: Write failing test**

```python
# tests/test_linkedin_publisher.py
"""Tests for LinkedIn publisher."""

import pytest
from unittest.mock import AsyncMock, patch

from src.linkedin_publisher import build_post_payload


def test_build_post_payload():
    """Payload follows LinkedIn Marketing API v2 format."""
    payload = build_post_payload(
        person_id="abc123",
        text="This is my LinkedIn post.",
    )
    assert payload["author"] == "urn:li:person:abc123"
    assert payload["lifecycleState"] == "PUBLISHED"
    assert payload["visibility"] == "PUBLIC"
    assert payload["commentary"] == "This is my LinkedIn post."
    assert payload["distribution"]["feedDistribution"] == "MAIN_FEED"


def test_build_post_payload_long_text():
    """Long text is included as-is (caller handles truncation)."""
    text = "x" * 3000
    payload = build_post_payload(person_id="abc", text=text)
    assert len(payload["commentary"]) == 3000
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
python -m pytest tests/test_linkedin_publisher.py -v
```

Expected: FAIL — module not found.

- [ ] **Step 3: Implement linkedin_publisher.py**

```python
# src/linkedin_publisher.py
"""LinkedIn Marketing API v2 — post publishing."""

from __future__ import annotations

import logging
import os
from datetime import datetime

import httpx
from dotenv import load_dotenv

load_dotenv()
logger = logging.getLogger(__name__)

LINKEDIN_API_BASE = "https://api.linkedin.com/rest/posts"


def _access_token() -> str:
    return os.getenv("LINKEDIN_ACCESS_TOKEN", "")


def _person_id() -> str:
    return os.getenv("LINKEDIN_PERSON_ID", "")


def build_post_payload(person_id: str, text: str) -> dict:
    """Build the LinkedIn post API payload."""
    return {
        "author": f"urn:li:person:{person_id}",
        "lifecycleState": "PUBLISHED",
        "visibility": "PUBLIC",
        "commentary": text,
        "distribution": {
            "feedDistribution": "MAIN_FEED",
        },
    }


async def publish_post(text: str) -> dict:
    """Publish a post to LinkedIn. Returns {"success": bool, "post_id": str, "error": str}."""
    token = _access_token()
    person_id = _person_id()

    if not token or not person_id:
        return {"success": False, "post_id": "", "error": "Missing LINKEDIN_ACCESS_TOKEN or LINKEDIN_PERSON_ID"}

    payload = build_post_payload(person_id, text)
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
        "X-Restli-Protocol-Version": "2.0.0",
        "LinkedIn-Version": "202401",
    }

    async with httpx.AsyncClient() as client:
        resp = await client.post(LINKEDIN_API_BASE, json=payload, headers=headers)

        if resp.status_code in (200, 201):
            # LinkedIn returns the post ID in the x-restli-id header
            post_id = resp.headers.get("x-restli-id", "")
            logger.info("Published to LinkedIn: %s", post_id)
            return {"success": True, "post_id": post_id, "error": ""}
        else:
            error = resp.text[:300]
            logger.error("LinkedIn publish failed %d: %s", resp.status_code, error)
            return {"success": False, "post_id": "", "error": f"HTTP {resp.status_code}: {error}"}
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
python -m pytest tests/test_linkedin_publisher.py -v
```

Expected: All 2 tests PASS.

- [ ] **Step 5: Commit**

```bash
git add src/linkedin_publisher.py tests/test_linkedin_publisher.py
git commit -m "feat: LinkedIn Marketing API v2 publisher"
```

---

### Task 9: Generate Entry Point (weekly pipeline)

**Files:**
- Create: `generate.py`
- Create: `tests/test_generate.py`

- [ ] **Step 1: Write failing test**

```python
# tests/test_generate.py
"""Integration test for the generate pipeline logic."""

import pytest
from datetime import date
from src.utils import get_week_dates


def test_get_week_dates_returns_5_days():
    """Week dates always returns exactly 5 weekdays."""
    days = get_week_dates(date(2026, 4, 20))  # Monday
    assert len(days) == 5
    assert days[0] == date(2026, 4, 20)
    assert days[4] == date(2026, 4, 24)


def test_get_week_dates_all_weekdays():
    """All returned dates are Mon-Fri."""
    days = get_week_dates(date(2026, 4, 20))
    for d in days:
        assert d.weekday() < 5  # 0=Mon, 4=Fri
```

- [ ] **Step 2: Run tests to verify they pass** (utils already implemented)

```bash
python -m pytest tests/test_generate.py -v
```

Expected: PASS (get_week_dates already exists in utils).

- [ ] **Step 3: Implement generate.py**

```python
#!/usr/bin/env python3
"""Weekly generation pipeline: research → generate → sheets → telegram.

Usage:
  python generate.py                  # Generate for this week
  python generate.py --week 2026-04-27  # Generate for a specific week
  python generate.py --dry-run        # Preview without writing
"""

import argparse
import asyncio
import logging
from datetime import date, datetime

from src.utils import setup_logging, get_week_dates
from src.search_client import YouSearchClient
from src.llm_client import LLMClient
from src.researcher import research_theme, build_research_summary
from src.post_generator import assign_themes_to_days, generate_post, check_similarity
from src.sheets_client import SheetsClient
from src import telegram_bot

logger = setup_logging("generate")


async def run_generate(week_start: date | None = None, dry_run: bool = False):
    """Main generation pipeline."""
    days = get_week_dates(week_start)
    week_str = days[0].isoformat()
    logger.info("=== Generating posts for week of %s ===", week_str)

    # Initialize clients
    sheets = SheetsClient()
    search = YouSearchClient()
    llm = LLMClient()

    try:
        # 1. Read settings and themes from Google Sheets
        settings = sheets.get_settings()
        themes_data = sheets.get_active_themes()
        theme_names = [t["theme"] for t in themes_data]

        if not theme_names:
            logger.error("Theme bank is empty. Add themes to the 'Theme Bank' tab.")
            await telegram_bot.send_notification("ERROR: Theme bank is empty. Cannot generate posts.")
            return

        logger.info("Settings: voice=%s, audience=%s", settings.get("voice"), settings.get("audience"))
        logger.info("Active themes: %d", len(theme_names))

        # 2. Assign themes to days
        assignments = assign_themes_to_days(theme_names, days)
        logger.info("Theme assignments:")
        for d, theme in assignments:
            logger.info("  %s (%s): %s", d.isoformat(), d.strftime("%A"), theme)

        if dry_run:
            logger.info("[DRY RUN] Would generate %d posts. Stopping.", len(assignments))
            return

        # 3. Research each theme
        research_data = {}
        for _, theme in assignments:
            if theme not in research_data:
                research_data[theme] = await research_theme(theme, search)

        # 4. Get prior published posts for dedup
        prior_posts = sheets.get_prior_posts(limit=5)
        prior_texts = [p.get("draft_text", "") for p in prior_posts if p.get("draft_text")]

        # 5. Generate posts
        generated_this_week = []
        for day, theme in assignments:
            weekday = day.strftime("%A")
            summary = build_research_summary(research_data.get(theme, {}))

            logger.info("Generating post for %s (%s): %s", day.isoformat(), weekday, theme)
            draft = await generate_post(
                llm=llm,
                theme=theme,
                day=day.isoformat(),
                weekday=weekday,
                settings=settings,
                research_summary=summary,
                prior_posts_this_week=generated_this_week,
                prior_published=prior_texts,
            )

            if not draft:
                logger.error("Failed to generate post for %s. Skipping.", theme)
                continue

            # Dedup check
            is_similar = await check_similarity(llm, draft, prior_texts + generated_this_week)
            if is_similar:
                logger.info("Regenerating %s with different angle...", theme)
                draft = await generate_post(
                    llm=llm,
                    theme=theme,
                    day=day.isoformat(),
                    weekday=weekday,
                    settings=settings,
                    research_summary=summary + "\n\nIMPORTANT: Take a COMPLETELY different angle. Avoid similar structure.",
                    prior_posts_this_week=generated_this_week,
                    prior_published=prior_texts,
                )

            if not draft:
                continue

            char_count = len(draft)
            generated_this_week.append(draft)

            # 6. Write to Google Sheets
            post_data = {
                "week_start": week_str,
                "day": day.isoformat(),
                "theme": theme,
                "draft_text": draft,
                "char_count": char_count,
                "research_summary": summary[:500],
                "status": "pending_approval",
                "suggested_time": "09:00 UTC",
            }
            sheets.append_post(post_data)

            # 7. Send to Telegram for approval
            # Find the row number (last row in Posts tab)
            posts_ws = sheets._ws("Posts")
            row_count = len(posts_ws.get_all_values())
            msg_id = await telegram_bot.send_draft(
                day=day.isoformat(),
                weekday=weekday,
                theme=theme,
                draft_text=draft,
                char_count=char_count,
                suggested_time="09:00 UTC",
                row_number=row_count,
            )
            if msg_id:
                sheets.update_post_status(row_count, "pending_approval", telegram_msg_id=msg_id)

        logger.info("=== Generation complete: %d posts created ===", len(generated_this_week))
        await telegram_bot.send_notification(
            f"Weekly batch ready: {len(generated_this_week)} posts for week of {week_str}. Please review and approve."
        )

    finally:
        await search.close()
        await llm.close()


def main():
    parser = argparse.ArgumentParser(description="Generate LinkedIn posts for the week")
    parser.add_argument("--week", type=str, help="Week start date (YYYY-MM-DD), defaults to next Monday")
    parser.add_argument("--dry-run", action="store_true", help="Preview without generating")
    args = parser.parse_args()

    week_start = None
    if args.week:
        week_start = date.fromisoformat(args.week)

    asyncio.run(run_generate(week_start=week_start, dry_run=args.dry_run))


if __name__ == "__main__":
    main()
```

- [ ] **Step 4: Commit**

```bash
git add generate.py tests/test_generate.py
git commit -m "feat: weekly generation pipeline entry point"
```

---

### Task 10: Approval Polling Entry Point

**Files:**
- Create: `poll_approvals.py`

- [ ] **Step 1: Implement poll_approvals.py**

```python
#!/usr/bin/env python3
"""Poll Telegram for approval/rejection callbacks and update Google Sheets.

Designed to run every 15 minutes via GitHub Actions.
"""

import asyncio
import json
import logging
import os
from pathlib import Path

from src.utils import setup_logging
from src.sheets_client import SheetsClient
from src import telegram_bot

logger = setup_logging("poll_approvals")

# Persist the last update_id to avoid reprocessing
OFFSET_FILE = Path("/tmp/telegram_offset.json")


def _load_offset() -> int:
    if OFFSET_FILE.exists():
        try:
            return json.loads(OFFSET_FILE.read_text()).get("offset", 0)
        except (json.JSONDecodeError, KeyError):
            pass
    return 0


def _save_offset(offset: int):
    OFFSET_FILE.write_text(json.dumps({"offset": offset}))


async def run_poll():
    """Poll Telegram for callback queries and process approve/reject actions."""
    logger.info("=== Polling Telegram for approvals ===")

    offset = _load_offset()
    updates = await telegram_bot.get_updates(offset=offset)

    if not updates:
        logger.info("No new callbacks. Done.")
        return

    logger.info("Found %d updates", len(updates))
    sheets = SheetsClient()

    for update in updates:
        update_id = update["update_id"]
        offset = update_id + 1  # Next poll starts after this

        callback = update.get("callback_query")
        if not callback:
            continue

        callback_id = callback["id"]
        data = callback.get("data", "")
        parsed = telegram_bot.parse_callback_data(data)

        if not parsed:
            await telegram_bot.answer_callback(callback_id, "Unknown action")
            continue

        action = parsed["action"]
        row = parsed["row"]
        logger.info("Processing: %s for row %d", action, row)

        if action == "approve":
            sheets.update_post_status(row, "approved")
            await telegram_bot.answer_callback(callback_id, "Approved!")
            await telegram_bot.send_notification(f"Post row {row} approved for publishing.")
            logger.info("Row %d approved", row)

        elif action == "reject":
            sheets.update_post_status(row, "rejected", feedback="Rejected via Telegram")
            await telegram_bot.answer_callback(callback_id, "Rejected. Add feedback in the sheet.")
            await telegram_bot.send_notification(
                f"Post row {row} rejected. Add feedback in the 'feedback' column of the Posts tab."
            )
            logger.info("Row %d rejected", row)

    _save_offset(offset)
    logger.info("=== Poll complete. Processed %d updates ===", len(updates))


def main():
    asyncio.run(run_poll())


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: Commit**

```bash
git add poll_approvals.py
git commit -m "feat: Telegram approval polling entry point"
```

---

### Task 11: Publish Entry Point

**Files:**
- Create: `publish.py`

- [ ] **Step 1: Implement publish.py**

```python
#!/usr/bin/env python3
"""Publish approved LinkedIn posts scheduled for today.

Designed to run weekdays at 09:00 UTC via GitHub Actions.
"""

import asyncio
import logging
from datetime import date, datetime

from src.utils import setup_logging
from src.sheets_client import SheetsClient
from src.linkedin_publisher import publish_post
from src import telegram_bot

logger = setup_logging("publish")


async def run_publish():
    """Find approved posts for today and publish to LinkedIn."""
    today = date.today().isoformat()
    logger.info("=== Publishing posts for %s ===", today)

    sheets = SheetsClient()
    approved = sheets.get_posts_by_status("approved")

    # Filter to today's posts
    todays_posts = [p for p in approved if p.get("day", "") == today]

    if not todays_posts:
        logger.info("No approved posts scheduled for today. Done.")
        return

    logger.info("Found %d approved posts for today", len(todays_posts))

    published = 0
    for post in todays_posts:
        row = post["_row"]
        draft = post.get("draft_text", "")
        theme = post.get("theme", "unknown")

        if not draft:
            logger.warning("Row %d has no draft text. Skipping.", row)
            continue

        logger.info("Publishing row %d: %s", row, theme)
        result = await publish_post(draft)

        if result["success"]:
            sheets.update_post_status(
                row, "published",
                linkedin_post_id=result["post_id"],
                published_at=datetime.now().isoformat(),
            )
            await telegram_bot.send_notification(f"Published: {theme} (row {row})")
            published += 1
            logger.info("Published row %d: %s", row, result["post_id"])
        else:
            logger.error("Failed to publish row %d: %s", row, result["error"])
            await telegram_bot.send_notification(f"FAILED to publish row {row}: {result['error']}")

    logger.info("=== Publish complete: %d/%d posted ===", published, len(todays_posts))


def main():
    asyncio.run(run_publish())


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: Commit**

```bash
git add publish.py
git commit -m "feat: LinkedIn publishing entry point for approved posts"
```

---

### Task 12: GitHub Actions Workflows

**Files:**
- Create: `.github/workflows/generate.yml`
- Create: `.github/workflows/approval-poll.yml`
- Create: `.github/workflows/publish.yml`

- [ ] **Step 1: Create generate.yml**

```yaml
# .github/workflows/generate.yml
name: Generate Weekly Posts

on:
  schedule:
    - cron: '0 6 * * 1'  # Monday 06:00 UTC
  workflow_dispatch:
    inputs:
      week:
        description: 'Week start date (YYYY-MM-DD)'
        required: false
      dry_run:
        description: 'Preview only (true/false)'
        required: false
        default: 'false'

jobs:
  generate:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - uses: actions/setup-python@v5
        with:
          python-version: '3.12'
          cache: 'pip'

      - run: pip install -r requirements.txt

      - name: Generate posts
        env:
          YOU_API_KEYS: ${{ secrets.YOU_API_KEYS }}
          HF_API_KEY: ${{ secrets.HF_API_KEY }}
          HF_MODEL: ${{ secrets.HF_MODEL }}
          HF_API_URL: ${{ secrets.HF_API_URL }}
          GOOGLE_SHEETS_CREDENTIALS: ${{ secrets.GOOGLE_SHEETS_CREDENTIALS }}
          GOOGLE_SHEET_ID: ${{ secrets.GOOGLE_SHEET_ID }}
          TELEGRAM_BOT_TOKEN: ${{ secrets.TELEGRAM_BOT_TOKEN }}
          TELEGRAM_CHAT_ID: ${{ secrets.TELEGRAM_CHAT_ID }}
        run: |
          ARGS=""
          if [ -n "${{ github.event.inputs.week }}" ]; then
            ARGS="$ARGS --week ${{ github.event.inputs.week }}"
          fi
          if [ "${{ github.event.inputs.dry_run }}" = "true" ]; then
            ARGS="$ARGS --dry-run"
          fi
          python generate.py $ARGS
```

- [ ] **Step 2: Create approval-poll.yml**

```yaml
# .github/workflows/approval-poll.yml
name: Poll Telegram Approvals

on:
  schedule:
    - cron: '*/15 * * * *'  # Every 15 minutes
  workflow_dispatch: {}

jobs:
  poll:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - uses: actions/setup-python@v5
        with:
          python-version: '3.12'
          cache: 'pip'

      - run: pip install -r requirements.txt

      - name: Poll for approvals
        env:
          GOOGLE_SHEETS_CREDENTIALS: ${{ secrets.GOOGLE_SHEETS_CREDENTIALS }}
          GOOGLE_SHEET_ID: ${{ secrets.GOOGLE_SHEET_ID }}
          TELEGRAM_BOT_TOKEN: ${{ secrets.TELEGRAM_BOT_TOKEN }}
          TELEGRAM_CHAT_ID: ${{ secrets.TELEGRAM_CHAT_ID }}
        run: python poll_approvals.py
```

- [ ] **Step 3: Create publish.yml**

```yaml
# .github/workflows/publish.yml
name: Publish Approved Posts

on:
  schedule:
    - cron: '0 9 * * 1-5'  # Weekdays 09:00 UTC
  workflow_dispatch: {}

jobs:
  publish:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - uses: actions/setup-python@v5
        with:
          python-version: '3.12'
          cache: 'pip'

      - run: pip install -r requirements.txt

      - name: Publish posts
        env:
          GOOGLE_SHEETS_CREDENTIALS: ${{ secrets.GOOGLE_SHEETS_CREDENTIALS }}
          GOOGLE_SHEET_ID: ${{ secrets.GOOGLE_SHEET_ID }}
          LINKEDIN_ACCESS_TOKEN: ${{ secrets.LINKEDIN_ACCESS_TOKEN }}
          LINKEDIN_PERSON_ID: ${{ secrets.LINKEDIN_PERSON_ID }}
          TELEGRAM_BOT_TOKEN: ${{ secrets.TELEGRAM_BOT_TOKEN }}
          TELEGRAM_CHAT_ID: ${{ secrets.TELEGRAM_CHAT_ID }}
        run: python publish.py
```

- [ ] **Step 4: Commit**

```bash
git add .github/workflows/
git commit -m "feat: GitHub Actions workflows for generate, poll, and publish"
```

---

### Task 13: Final Integration Test and Cleanup

- [ ] **Step 1: Run all tests**

```bash
cd /Users/abhisheshmishra/linkedin-post-scheduler
python -m pytest tests/ -v
```

Expected: All tests PASS.

- [ ] **Step 2: Verify project structure**

```bash
find . -type f -not -path './.git/*' -not -path './__pycache__/*' | sort
```

Expected output should match the file map from the spec.

- [ ] **Step 3: Final commit**

```bash
git add -A
git commit -m "chore: final cleanup and integration verification"
```
