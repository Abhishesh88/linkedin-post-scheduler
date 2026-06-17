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
                        logger.error("Qwen error %d: %s", resp.status, error_text[:500])
                        # Don't retry on 400 "model not supported" — it won't resolve with retries
                        if resp.status == 400 and "model_not_supported" in error_text:
                            logger.error("Model '%s' is not supported. Check HF provider settings or update HF_MODEL.", self.hf_model)
                            return LLMResponse(
                                text="", model=self.hf_model,
                                latency=time.time() - start, error="model_not_supported",
                            )
                        if attempt < len(retry_delays):
                            delay = retry_delays[attempt] + random.uniform(1, 5)
                            logger.warning("Retrying in %.1fs (attempt %d)", delay, attempt + 1)
                            await asyncio.sleep(delay)
                            continue
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
