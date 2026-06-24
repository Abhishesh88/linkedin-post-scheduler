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
                    # Hard timeout — the SDK has none, so a stuck request would hang
                    # the whole batch_search gather (and the CI job) indefinitely.
                    sdk_res = await asyncio.wait_for(
                        you.search.unified_async(**kwargs), timeout=30
                    )
                key.total_calls += 1
                return self._parse_sdk_response(query, sdk_res)
            except asyncio.TimeoutError:
                key.errors += 1
                self._cooldown_key(key)
                logger.warning("Search timed out (30s) for '%s'", query[:50])
                return SearchResponse(query=query, web_results=[], news_results=[], error="timeout")
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
