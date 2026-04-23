"""LLM Ensemble Agent - uses multiple LLMs as research sources."""

from __future__ import annotations

import asyncio
import logging
import os
from datetime import datetime, timezone
from typing import Any, Optional

logger = logging.getLogger("aria")


class LLMEnsembleAgent:
    """Queries multiple LLM models in parallel to generate research content.

    Each model is treated as a source that "knows" about the topic.
    Responses are collected as documents with source_type='llm_response'.
    """

    SYSTEM_PROMPT = (
        "You are a research assistant. Provide detailed, factual information about the given topic. "
        "Include key findings, data points, mechanisms, notable examples, and current state of knowledge. "
        "Be thorough and cite sources or context where relevant. "
        "Format your response as flowing text with clear sections."
    )

    def __init__(
        self,
        models: list[dict] | None = None,
        shared_memory: Any = None,
        # Legacy / extended constructor params (used by tests and advanced callers)
        mission: dict | None = None,
        settings: Any = None,
        logger: Any = None,
        cleaner: Any = None,
        persist_document: Any = None,
        emit: Any = None,
        record_metric: Any = None,
    ) -> None:
        """Initialize the ensemble agent.

        Accepts either the simple ``models`` list or the full mission-based
        constructor so both the orchestrator and the test suite can construct
        the agent without changes.
        """
        if models is not None:
            self._models = models
        elif mission is not None:
            # Extract model list from mission dict
            llm_cfg = mission.get("llm_sources", {})
            self._models = [m for m in llm_cfg.get("models", []) if m.get("enabled", True)]
        else:
            self._models = []

        self._shared_memory = shared_memory
        self._settings = settings
        self._log = logger or logging.getLogger("aria")
        self._cleaner = cleaner
        self._persist_document = persist_document
        self._emit_fn = emit
        self._record_metric = record_metric

        # Determine the "cleaning brain" model to exclude from ensemble
        self._brain_provider = ""
        self._brain_model = ""
        if settings is not None:
            provider = getattr(settings, "llm_provider", "")
            if provider == "ollama":
                self._brain_model = getattr(settings, "ollama_model", "")
                self._brain_provider = "ollama"
            else:
                self._brain_model = getattr(settings, f"{provider}_model", "")
                self._brain_provider = provider

    @property
    def enabled_models(self) -> list[dict]:
        """Return the list of enabled models, excluding the cleaning brain."""
        result = []
        for m in self._models:
            if not m.get("enabled", True):
                continue
            # Skip the model used for cleaning
            if (
                self._brain_model
                and m.get("model_id") == self._brain_model
                and m.get("provider", "") == self._brain_provider
            ):
                continue
            result.append(m)
        return result

    async def collect(self, queries: list[str]) -> list[dict]:
        """Query all models for each query in parallel.

        Args:
            queries: Research queries to send to all models.

        Returns:
            List of document dicts from all model responses.
        """
        tasks = []
        for query in queries:
            for model_cfg in self._models:
                if not model_cfg.get("enabled", True):
                    continue
                tasks.append(self._query_model(query, model_cfg))

        results = await asyncio.gather(*tasks, return_exceptions=True)
        docs = []
        for r in results:
            if isinstance(r, Exception):
                logger.warning("LLMEnsembleAgent: task failed: %s", r)
            elif r is not None:
                docs.append(r)
        return docs

    async def _query_model(self, query: str, model_cfg: dict) -> Optional[dict]:
        """Send a query to a single model and return a document dict."""
        provider = model_cfg.get("provider", "openrouter")
        model_id = model_cfg.get("model_id", "")
        base_url = model_cfg.get("base_url")
        api_key = model_cfg.get("api_key")
        max_tokens = model_cfg.get("max_tokens", 1500)
        temperature = model_cfg.get("temperature", 0.3)

        try:
            response_text = await self._call_llm(
                query=query,
                provider=provider,
                model_id=model_id,
                base_url=base_url,
                api_key=api_key,
                max_tokens=max_tokens,
                temperature=temperature,
            )

            if not response_text:
                return None

            return {
                "url": "",
                "title": f"LLM Research: {query[:80]}",
                "text": response_text,
                "source_type": "llm_response",
                "platform": provider,
                "language": "en",
                "word_count": len(response_text.split()),
                "collected_at": datetime.now(timezone.utc).isoformat(),
                "metadata": {
                    "query": query,
                    "model_id": model_id,
                    "provider": provider,
                    "max_tokens": max_tokens,
                    "temperature": temperature,
                },
            }
        except Exception as exc:
            logger.warning(
                "LLMEnsembleAgent: error querying %s/%s for '%s': %s",
                provider, model_id, query, exc,
            )
            return None

    async def _call_llm(
        self,
        query: str,
        provider: str,
        model_id: str,
        base_url: Optional[str],
        api_key: Optional[str],
        max_tokens: int,
        temperature: float,
    ) -> Optional[str]:
        """Dispatch an LLM call to the appropriate provider."""
        prompt = (
            f"Please provide comprehensive research information about the following topic:\n\n"
            f"{query}\n\n"
            f"Cover: key concepts, current state of research, important findings, "
            f"notable organizations or researchers, challenges, and future directions."
        )

        if provider == "anthropic":
            return await self._call_anthropic(
                prompt, model_id, api_key or os.getenv("ANTHROPIC_API_KEY", ""),
                max_tokens, temperature
            )
        else:
            # OpenAI-compatible (openrouter, openai, ollama)
            resolved_key = api_key or _resolve_api_key(provider)
            resolved_base = base_url or _resolve_base_url(provider)
            return await self._call_openai_compat(
                prompt, model_id, resolved_key, resolved_base, max_tokens, temperature
            )

    async def _call_openai_compat(
        self,
        prompt: str,
        model_id: str,
        api_key: str,
        base_url: Optional[str],
        max_tokens: int,
        temperature: float,
    ) -> Optional[str]:
        from openai import AsyncOpenAI

        kwargs = {"api_key": api_key or "sk-nokey"}
        if base_url:
            kwargs["base_url"] = base_url

        client = AsyncOpenAI(**kwargs)
        try:
            resp = await client.chat.completions.create(
                model=model_id,
                messages=[
                    {"role": "system", "content": self.SYSTEM_PROMPT},
                    {"role": "user", "content": prompt},
                ],
                max_tokens=max_tokens,
                temperature=temperature,
            )
            return resp.choices[0].message.content if resp.choices else None
        finally:
            await client.close()

    async def _call_anthropic(
        self,
        prompt: str,
        model_id: str,
        api_key: str,
        max_tokens: int,
        temperature: float,
    ) -> Optional[str]:
        from anthropic import AsyncAnthropic

        client = AsyncAnthropic(api_key=api_key)
        try:
            resp = await client.messages.create(
                model=model_id,
                max_tokens=max_tokens,
                temperature=temperature,
                system=self.SYSTEM_PROMPT,
                messages=[{"role": "user", "content": prompt}],
            )
            return resp.content[0].text if resp.content else None
        finally:
            await client.close()


_VALID_PROVIDERS = frozenset({"openrouter", "openai", "anthropic", "ollama"})


def _resolve_api_key(provider: str) -> str:
    """Resolve API key from environment for a given provider.

    Raises ValueError for unknown provider names to catch typos early.
    """
    provider = provider.strip().lower()
    if provider not in _VALID_PROVIDERS:
        raise ValueError(
            f"Unknown LLM provider '{provider}'. "
            f"Valid options: {sorted(_VALID_PROVIDERS)}"
        )
    mapping = {
        "openrouter": "OPENROUTER_API_KEY",
        "openai": "OPENAI_API_KEY",
        "anthropic": "ANTHROPIC_API_KEY",
        "ollama": None,
    }
    env_var = mapping.get(provider)
    if env_var:
        return os.getenv(env_var, "sk-nokey")
    return "ollama"  # Ollama uses a dummy key


def _resolve_base_url(provider: str) -> Optional[str]:
    """Resolve base URL for a given provider."""
    provider = provider.strip().lower()
    mapping = {
        "openrouter": "https://openrouter.ai/api/v1",
        "openai": "https://api.openai.com/v1",
        "anthropic": None,  # Anthropic SDK handles its own endpoint
        "ollama": os.getenv("OLLAMA_BASE_URL", "http://localhost:11434") + "/v1",
    }
    return mapping.get(provider)
