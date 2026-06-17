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
