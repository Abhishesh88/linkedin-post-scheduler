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
