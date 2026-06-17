# Instagram Claude Research — Design Spec

## Goal

Improve Instagram research queries in the post generation pipeline to discover trending Claude ecosystem content and extract real problem-solution patterns for LinkedIn posts.

## Approach

Replace the single generic Instagram query in `researcher.py` with 2-3 adaptive queries that are Claude-focused when the theme category is AI-related, and general otherwise.

## Category Detection

A constant set defines which Theme Bank categories trigger Claude-focused queries:

```python
AI_CATEGORIES = {"ai tools", "ai agents", "developer productivity", "system design", "llm"}
```

Detection: `theme_category.lower() in AI_CATEGORIES`

No LLM call needed — uses the existing `category` field from Theme Bank.

## Query Design

### AI/tools themes (category in AI_CATEGORIES) — 3 Instagram queries:

1. **Claude problem-solving**: `site:instagram.com Claude Code {theme_keyword} tutorial demo {year}`
2. **Claude ecosystem**: `site:instagram.com Claude MCP skills agents workflow {year}`
3. **Community discussions**: `site:instagram.com Anthropic Claude tips tricks developer {theme_keyword}`

### Non-AI themes — 1 Instagram query:

1. `site:instagram.com {theme_keyword} tips insights {year}`

`theme_keyword` = `theme.split("-")[0].strip()` (existing logic).

Total queries per theme: 7-8 for AI themes, 6 for non-AI themes (up from 6 for all).

## Research Summary Integration

No changes. Instagram results already flow through `_serialize_results()` into `build_research_summary()`. The system prompt already instructs the LLM to "Reference what's trending on social media and developer communities."

## Files Changed

### `src/researcher.py`
- Add `AI_CATEGORIES` constant at module level
- Modify `build_research_queries(theme, category)` — add `category` parameter
- Replace single Instagram query with adaptive logic (3 queries for AI categories, 1 for others)
- Update `research_theme(theme, search_client, category)` to accept and pass `category`

### `generate.py`
- Pass `category` to `research_theme()` (already available from theme entry)

### `tests/test_researcher.py`
- Update `test_build_queries_returns_4_per_theme` to reflect new query count and `category` parameter
- Add test for AI category query generation (should produce more queries)
- Add test for non-AI category query generation

## No Other Changes

- No new files or dependencies
- Search client unchanged — receives more queries via `batch_search()`
- Post generation pipeline unchanged
- Prompt templates unchanged
- Google Sheets schema unchanged
