# Instagram Claude Research Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the generic Instagram search query with adaptive Claude-focused queries when the theme category is AI-related.

**Architecture:** Add `AI_CATEGORIES` constant and `category` parameter to `build_research_queries()` and `research_theme()`. For AI categories, generate 3 targeted Instagram queries; for others, 1 general query. Caller (`generate.py`) passes the existing `category` field through.

**Tech Stack:** Python, You.com search API (existing)

---

### Task 1: Update `build_research_queries` with category-aware Instagram queries

**Files:**
- Modify: `src/researcher.py:14-24`
- Test: `tests/test_researcher.py`

- [ ] **Step 1: Write failing tests for the new category parameter**

Replace the entire contents of `tests/test_researcher.py` with:

```python
"""Tests for topic and competitor research."""

from src.researcher import build_research_queries, build_research_summary


def test_build_queries_ai_category_returns_8():
    """AI-category themes produce 8 research queries (5 base + 3 Instagram)."""
    queries = build_research_queries("Claude Code productivity tips", category="AI Tools")
    assert len(queries) == 8


def test_build_queries_non_ai_category_returns_6():
    """Non-AI-category themes produce 6 research queries (5 base + 1 Instagram)."""
    queries = build_research_queries("Remote engineering teams", category="Remote work")
    assert len(queries) == 6


def test_build_queries_empty_category_returns_6():
    """Empty category defaults to non-AI behavior."""
    queries = build_research_queries("Technical debt", category="")
    assert len(queries) == 6


def test_build_queries_ai_category_includes_claude():
    """AI-category queries include Claude-specific Instagram searches."""
    queries = build_research_queries("MCP server patterns", category="AI Agents")
    instagram_queries = [q for q in queries if "instagram.com" in q.lower()]
    assert len(instagram_queries) == 3
    claude_queries = [q for q in instagram_queries if "claude" in q.lower() or "anthropic" in q.lower()]
    assert len(claude_queries) >= 2


def test_build_queries_non_ai_category_instagram():
    """Non-AI-category themes get 1 general Instagram query."""
    queries = build_research_queries("Leadership lessons", category="Leadership")
    instagram_queries = [q for q in queries if "instagram.com" in q.lower()]
    assert len(instagram_queries) == 1
    assert "claude" not in instagram_queries[0].lower()


def test_build_queries_include_linkedin():
    """At least one query targets LinkedIn for competitor research."""
    queries = build_research_queries("Technical debt", category="Delivery")
    linkedin_queries = [q for q in queries if "linkedin.com" in q.lower()]
    assert len(linkedin_queries) >= 1


def test_build_queries_include_year():
    """Queries include the current year for freshness."""
    queries = build_research_queries("System design", category="System Design")
    year_queries = [q for q in queries if "2026" in q]
    assert len(year_queries) >= 1


def test_build_queries_category_case_insensitive():
    """Category matching is case-insensitive."""
    queries_lower = build_research_queries("AI topic", category="ai tools")
    queries_upper = build_research_queries("AI topic", category="AI Tools")
    assert len(queries_lower) == len(queries_upper)


def test_build_research_summary_truncates():
    """Summary respects max_chars limit."""
    snippets = [{"text": "x" * 500, "source": f"http://example.com/{i}", "title": f"T{i}"} for i in range(20)]
    data = {"total_sources": 20, "total_snippets": 20, "sources": [], "all_snippets": snippets}
    summary = build_research_summary(data, max_chars=1000)
    assert len(summary) <= 1020


def test_build_research_summary_empty_data():
    """Empty research data produces minimal summary."""
    data = {"total_sources": 0, "total_snippets": 0, "sources": [], "all_snippets": []}
    summary = build_research_summary(data)
    assert "Sources found: 0" in summary
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python3 -m pytest tests/test_researcher.py -v`
Expected: Multiple FAIL — `build_research_queries()` doesn't accept `category` parameter yet.

- [ ] **Step 3: Implement the category-aware query logic**

Replace `src/researcher.py` lines 1-24 with:

```python
"""Research strategy: topic + LinkedIn competitor research via You.com."""

from __future__ import annotations

import logging
from datetime import datetime

from .search_client import YouSearchClient, SearchResponse
from .utils import current_year

logger = logging.getLogger(__name__)

AI_CATEGORIES = {"ai tools", "ai agents", "developer productivity", "system design", "llm"}


def build_research_queries(theme: str, category: str = "") -> list[str]:
    """Generate research queries per theme. AI categories get Claude-focused Instagram queries."""
    year = current_year()
    theme_keyword = theme.split("-")[0].strip()
    is_ai = category.strip().lower() in AI_CATEGORIES

    # 5 base queries (non-Instagram)
    queries = [
        f'"{theme}" {year} trending AI tools',
        f'site:linkedin.com "{theme}" AI tools developer',
        f'"{theme}" viral developer tools {year}',
        f'new AI tools {theme_keyword} launched {year}',
        f'"{theme}" comparison review developer experience {year}',
    ]

    # Instagram queries — adaptive based on category
    if is_ai:
        queries.extend([
            f'site:instagram.com Claude Code {theme_keyword} tutorial demo {year}',
            f'site:instagram.com Claude MCP skills agents workflow {year}',
            f'site:instagram.com Anthropic Claude tips tricks developer {theme_keyword}',
        ])
    else:
        queries.append(
            f'site:instagram.com {theme_keyword} tips insights {year}'
        )

    return queries
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python3 -m pytest tests/test_researcher.py -v`
Expected: All 11 tests PASS.

- [ ] **Step 5: Commit**

```bash
git add src/researcher.py tests/test_researcher.py
git commit -m "feat: category-aware Instagram queries with Claude focus for AI themes"
```

---

### Task 2: Pass `category` through `research_theme` and `generate.py`

**Files:**
- Modify: `src/researcher.py:87-95`
- Modify: `generate.py:92`

- [ ] **Step 1: Update `research_theme` to accept and pass `category`**

In `src/researcher.py`, replace the `research_theme` function (lines 87-95) with:

```python
async def research_theme(theme: str, search_client: YouSearchClient, category: str = "") -> dict:
    """Research a single theme. Returns serialized research data."""
    queries = build_research_queries(theme, category=category)
    logger.info("Researching '%s' [%s] with %d queries", theme, category or "no category", len(queries))
    responses = await search_client.batch_search(queries)
    data = _serialize_results(responses)
    data["theme"] = theme
    logger.info("Research done: '%s' — %d sources, %d snippets", theme, data["total_sources"], data["total_snippets"])
    return data
```

- [ ] **Step 2: Update `generate.py` to pass `category` to `research_theme`**

In `generate.py`, change line 92 from:

```python
        data = await research_theme(theme, search)
```

to:

```python
        data = await research_theme(theme, search, category=category)
```

- [ ] **Step 3: Run all tests to verify nothing broke**

Run: `python3 -m pytest tests/ -v`
Expected: All tests PASS (the pre-existing `test_build_queries_returns_4_per_theme` is now replaced).

- [ ] **Step 4: Commit**

```bash
git add src/researcher.py generate.py
git commit -m "feat: pass category through research_theme to enable adaptive queries"
```

---

### Task 3: Update `poll_approvals.py` reject handler to pass category

**Files:**
- Modify: `poll_approvals.py:133`

The reject handler in `poll_approvals.py` also calls `research_theme`. It already resolves the category from Theme Bank (line 114-119). Pass it through.

- [ ] **Step 1: Update the `research_theme` call in `_handle_reject`**

In `poll_approvals.py`, change line 133 from:

```python
        data = await research_theme(theme, search)
```

to:

```python
        data = await research_theme(theme, search, category=category)
```

- [ ] **Step 2: Run tests to verify nothing broke**

Run: `python3 -m pytest tests/ -v`
Expected: All tests PASS.

- [ ] **Step 3: Commit**

```bash
git add poll_approvals.py
git commit -m "feat: pass category in reject handler for adaptive research queries"
```
