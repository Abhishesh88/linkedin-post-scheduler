"""Tests for topic and competitor research."""

from src.researcher import build_research_queries, build_research_summary


def test_build_queries_ai_category_returns_8():
    """AI-category themes produce 8 research queries (3 base + 3 news + 2 Instagram)."""
    queries = build_research_queries("Claude Code productivity tips", category="AI Tools")
    assert len(queries) == 8


def test_build_queries_non_ai_category_returns_6():
    """Non-AI-category themes produce 6 research queries (3 base + 2 theme + 1 Instagram)."""
    queries = build_research_queries("Remote engineering teams", category="Remote work")
    assert len(queries) == 6


def test_build_queries_empty_category_returns_6():
    """Empty category defaults to non-AI behavior."""
    queries = build_research_queries("Technical debt", category="")
    assert len(queries) == 6


def test_build_queries_ai_category_includes_comparisons():
    """AI-category queries include tool comparisons and trending news."""
    queries = build_research_queries("MCP server patterns", category="AI Agents")
    comparison_queries = [q for q in queries if "vs" in q.lower() or "comparison" in q.lower() or "trending" in q.lower() or "news" in q.lower()]
    assert len(comparison_queries) >= 2


def test_build_queries_ai_category_includes_instagram():
    """AI-category queries include Instagram searches."""
    queries = build_research_queries("MCP server patterns", category="AI Agents")
    instagram_queries = [q for q in queries if "instagram.com" in q.lower()]
    assert len(instagram_queries) == 2


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
