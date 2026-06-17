"""Tests for LinkedIn publisher."""

import pytest
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
