"""Async LLM client (OpenAI-compatible chat completions).

Defaults to Ollama Cloud `gemma4:31b-cloud`; HuggingFace (Qwen) available as a
fallback. Both providers expose the same /v1/chat/completions shape, so one code
path serves both — pick with LLM_PROVIDER (ollama|hf).
"""

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


# OpenAI-compatible provider presets
_PROVIDERS = {
    "ollama": {
        "url_env": "OLLAMA_API_URL", "url": "https://ollama.com/v1/chat/completions",
        "model_env": "OLLAMA_MODEL", "model": "gemma4:31b-cloud",
        "key_env": "OLLAMA_API_KEY",
    },
    "hf": {
        "url_env": "HF_API_URL", "url": "https://router.huggingface.co/v1/chat/completions",
        "model_env": "HF_MODEL", "model": "Qwen/Qwen3-235B-A22B",
        "key_env": "HF_API_KEY",
    },
}


class LLMClient:
    """Async OpenAI-compatible chat client. Defaults to Ollama Cloud (gemma4)."""

    def __init__(self, max_concurrent: int = 4):
        self.provider = os.getenv("LLM_PROVIDER", "ollama").lower()
        preset = _PROVIDERS.get(self.provider, _PROVIDERS["ollama"])

        self.model = os.getenv(preset["model_env"], preset["model"])
        self.api_url = os.getenv(preset["url_env"], preset["url"])
        # Ollama Cloud key falls back to HF_API_KEY for compatibility with prior setups
        self.api_key = os.getenv(preset["key_env"]) or (
            os.getenv("HF_API_KEY") if self.provider == "ollama" else None
        )

        self.semaphore = asyncio.Semaphore(max_concurrent)
        self._session: aiohttp.ClientSession | None = None
        logger.info("LLMClient provider=%s model=%s", self.provider, self.model)

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
        """Strip <think>...</think> tags from thinking-model output."""
        return re.sub(r"<think>.*?</think>", "", text, flags=re.DOTALL).strip()

    async def generate(
        self,
        user_prompt: str,
        system_prompt: str = "",
        temperature: float = 0.5,
        max_tokens: int = 2000,
    ) -> LLMResponse:
        """Call the configured chat model with retry logic."""
        async with self.semaphore:
            start = time.time()
            messages = []
            sys_content = system_prompt
            # /no_think only applies to Qwen3 thinking models — skip for gemma/others
            if sys_content and "qwen" in self.model.lower() and "/no_think" not in sys_content:
                sys_content = sys_content.rstrip() + " /no_think"
            if sys_content:
                messages.append({"role": "system", "content": sys_content})
            messages.append({"role": "user", "content": user_prompt})

            payload = {
                "model": self.model,
                "messages": messages,
                "max_tokens": max_tokens,
                "temperature": temperature,
                "stream": False,
            }
            # frequency_penalty is HF/OpenAI-specific; the proven Ollama Cloud call omits it
            if self.provider == "hf":
                payload["frequency_penalty"] = 0.3

            headers = {
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
            }

            retry_delays = [5, 15, 30, 60]
            session = await self._get_session()

            for attempt in range(len(retry_delays) + 1):
                try:
                    async with session.post(self.api_url, json=payload, headers=headers) as resp:
                        if resp.status == 200:
                            data = await resp.json()
                            content = data["choices"][0]["message"]["content"] or ""
                            text = self._strip_thinking(content)
                            latency = time.time() - start
                            logger.info("%s call: %.1fs, %d chars", self.provider, latency, len(text))
                            return LLMResponse(text=text, model=self.model, latency=latency)

                        if resp.status in (429, 503) and attempt < len(retry_delays):
                            delay = retry_delays[attempt] + random.uniform(1, 5)
                            logger.warning("LLM %d, retry in %.1fs (attempt %d)", resp.status, delay, attempt + 1)
                            await asyncio.sleep(delay)
                            continue

                        error_text = await resp.text()
                        logger.error("LLM error %d: %s", resp.status, error_text[:500])
                        # Don't retry on "model not supported" — won't resolve with retries
                        if resp.status == 400 and "model_not_supported" in error_text:
                            logger.error("Model '%s' not supported by provider '%s'.", self.model, self.provider)
                            return LLMResponse(
                                text="", model=self.model,
                                latency=time.time() - start, error="model_not_supported",
                            )
                        # Non-retryable auth/billing errors — retrying just wastes time
                        if resp.status in (401, 402, 403, 404):
                            reason = {401: "auth_failed", 402: "credits_depleted",
                                      403: "forbidden", 404: "not_found"}[resp.status]
                            logger.error("Non-retryable LLM error %d (%s) — aborting. Check %s/model or switch LLM_PROVIDER.",
                                         resp.status, reason, _PROVIDERS[self.provider]["key_env"] if self.provider in _PROVIDERS else "API key")
                            return LLMResponse(
                                text="", model=self.model,
                                latency=time.time() - start, error=reason,
                            )
                        if attempt < len(retry_delays):
                            delay = retry_delays[attempt] + random.uniform(1, 5)
                            logger.warning("Retrying in %.1fs (attempt %d)", delay, attempt + 1)
                            await asyncio.sleep(delay)
                            continue
                        break

                except Exception as e:
                    logger.error("LLM exception (attempt %d): %s", attempt + 1, e)
                    if attempt < len(retry_delays):
                        await asyncio.sleep(retry_delays[attempt])
                        continue
                    break

            return LLMResponse(
                text="", model=self.model,
                latency=time.time() - start, error="LLM unavailable after retries",
            )
