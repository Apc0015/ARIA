"""LLM routing helpers."""

from __future__ import annotations

from typing import Any

from aria.brain.cleaner import LLMBrain
from aria.config import load_config
from aria.utils.logger import configure_logging


class LLMRouter:
    """Thin wrapper around the configured cleaning brain provider."""

    def __init__(self, settings: Any | None = None, logger: Any | None = None) -> None:
        self.settings = settings or load_config()
        self.logger = logger or configure_logging()
        self.brain = LLMBrain(self.settings, self.logger)

    def call(self, prompt: str, system_prompt: str) -> str | None:
        return self.brain.call_llm(prompt, system_prompt)

    async def call_async(self, prompt: str, system_prompt: str) -> str | None:
        return await self.brain.call_llm_async(prompt, system_prompt)


def call_llm(prompt: str, system_prompt: str, settings: Any | None = None, logger: Any | None = None) -> str | None:
    """Convenience wrapper for one-off LLM calls."""

    return LLMRouter(settings=settings, logger=logger).call(prompt, system_prompt)


async def call_llm_async(prompt: str, system_prompt: str, settings: Any | None = None, logger: Any | None = None) -> str | None:
    """Async convenience wrapper for one-off LLM calls."""

    return await LLMRouter(settings=settings, logger=logger).call_async(prompt, system_prompt)
