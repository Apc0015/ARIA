"""Smart Cleaning Agent - uses LLM to extract structured data from raw documents."""

from __future__ import annotations

import asyncio
import json
import logging
import re
from typing import Any, Optional

from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
    before_sleep_log,
)

from aria.engine.ensemble.providers import resolve_cleaning_llm

logger = logging.getLogger("aria")

_CONTENT_TYPES = [
    "academic_paper",
    "news_article",
    "forum_post",
    "social_media",
    "technical_doc",
    "video_transcript",
    "encyclopedia",
    "opinion_essay",
    "gov_policy",
    "data_report",
]

_CLEANING_SYSTEM = (
    "You are a document analysis and information extraction system. "
    "Your job is to analyse research documents and extract structured information. "
    "Always respond with valid JSON only. No markdown, no explanation."
)


class LLMCleaner:
    """Cleans and structures raw documents using an LLM.

    Makes one LLM call per document that:
    1. Detects content type (from 10 fixed categories)
    2. Scores relevance against the research goal (0.0-1.0)
    3. Extracts all fields defined in the output_schema
    4. Generates a concise summary
    """

    def __init__(self, config: Any, logger: Optional[Any] = None) -> None:
        self._config = config
        self._log = logger or logging.getLogger("aria")
        self._provider, self._model_id, self._base_url, self._api_key = resolve_cleaning_llm(config)

    async def clean_document(
        self,
        doc: dict,
        instructions: str,
        output_schema: dict,
    ) -> dict:
        """Clean a single document.

        Args:
            doc: Raw document dict.
            instructions: Cleaning instructions from the mission.
            output_schema: Dict describing expected output fields.

        Returns:
            Enriched document dict with all schema fields populated.
        """
        if not self._api_key and self._provider not in ("ollama",):
            return _fallback_clean(doc, output_schema)

        try:
            prompt = _build_cleaning_prompt(doc, instructions, output_schema)
            response_text = await self._call_llm(prompt)
            if not response_text:
                return _fallback_clean(doc, output_schema)

            extracted = _parse_llm_json(response_text)
            if not extracted:
                return _fallback_clean(doc, output_schema)

            return _merge_doc_with_extraction(doc, extracted, output_schema)

        except Exception as exc:
            self._log.warning("LLMCleaner: error cleaning doc '%s': %s", doc.get("url", ""), exc)
            return _fallback_clean(doc, output_schema)

    async def clean_one(
        self,
        doc: dict,
        instructions: str,
        output_schema: dict,
    ) -> dict:
        """Public alias for clean_document — used by StreamingPipeline."""
        return await self.clean_document(doc, instructions, output_schema)

    async def clean_batch(
        self,
        docs: list[dict],
        instructions: str,
        output_schema: dict,
        concurrency: int = 5,
        on_progress: Optional[Any] = None,
    ) -> list[dict]:
        """Clean a batch of documents with bounded concurrency.

        Args:
            docs:         List of raw document dicts.
            instructions: Cleaning instructions from the mission.
            output_schema: Output schema dict.
            concurrency:  Max parallel LLM calls.
            on_progress:  Optional async callable(completed: int, total: int)
                          called after each document finishes cleaning.

        Returns:
            List of cleaned document dicts in the same order as input.
        """
        sem = asyncio.Semaphore(concurrency)
        total = len(docs)
        completed = 0

        async def _clean_one(doc: dict) -> dict:
            nonlocal completed
            async with sem:
                result = await self.clean_document(doc, instructions, output_schema)
                await asyncio.sleep(0.1)  # small backoff between calls
                completed += 1
                if on_progress:
                    try:
                        await on_progress(completed, total)
                    except Exception:
                        pass
                return result

        tasks = [_clean_one(d) for d in docs]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        cleaned = []
        for i, r in enumerate(results):
            if isinstance(r, Exception):
                self._log.warning("LLMCleaner: batch item %d failed: %s", i, r)
                cleaned.append(_fallback_clean(docs[i], output_schema))
            else:
                cleaned.append(r)
        return cleaned

    async def _call_llm(self, prompt: str) -> Optional[str]:
        """Route LLM call to the correct provider."""
        if self._provider == "anthropic":
            return await _call_anthropic(
                prompt, self._model_id, self._api_key, _CLEANING_SYSTEM
            )
        else:
            return await _call_openai_compat(
                prompt, self._model_id, self._api_key, self._base_url, _CLEANING_SYSTEM
            )


class _LLMRateLimitError(Exception):
    """Raised when the LLM provider returns a rate-limit response (429/529)."""


class _LLMTransientError(Exception):
    """Raised on transient server errors (500/502/503/504) worth retrying."""


def _classify_openai_error(exc: Exception) -> Exception:
    """Re-raise as a typed error so tenacity can target retries correctly."""
    msg = str(exc).lower()
    if "429" in msg or "rate limit" in msg or "too many requests" in msg:
        raise _LLMRateLimitError(str(exc)) from exc
    if any(c in msg for c in ("500", "502", "503", "504", "timeout", "connection")):
        raise _LLMTransientError(str(exc)) from exc
    raise exc


@retry(
    retry=retry_if_exception_type((_LLMRateLimitError, _LLMTransientError)),
    wait=wait_exponential(multiplier=1, min=2, max=30),
    stop=stop_after_attempt(4),
    before_sleep=before_sleep_log(logger, logging.DEBUG),
    reraise=False,
)
async def _call_openai_compat(
    prompt: str,
    model_id: str,
    api_key: str,
    base_url: Optional[str],
    system: str,
    max_tokens: int = 2500,
    temperature: float = 0.1,
) -> Optional[str]:
    from openai import AsyncOpenAI

    kwargs: dict[str, Any] = {"api_key": api_key or "sk-nokey"}
    if base_url:
        kwargs["base_url"] = base_url

    client = AsyncOpenAI(**kwargs)
    try:
        # Try with json_object response format first (not all providers support it)
        try:
            resp = await client.chat.completions.create(
                model=model_id,
                messages=[
                    {"role": "system", "content": system},
                    {"role": "user", "content": prompt},
                ],
                max_tokens=max_tokens,
                temperature=temperature,
                response_format={"type": "json_object"},
            )
        except Exception as exc:
            _classify_openai_error(exc)
            resp = await client.chat.completions.create(
                model=model_id,
                messages=[
                    {"role": "system", "content": system},
                    {"role": "user", "content": prompt},
                ],
                max_tokens=max_tokens,
                temperature=temperature,
            )
        return resp.choices[0].message.content if resp.choices else None
    except (_LLMRateLimitError, _LLMTransientError):
        raise  # let tenacity handle these
    except Exception as exc:
        logger.debug("OpenAI-compat call failed: %s", exc)
        return None
    finally:
        await client.close()


@retry(
    retry=retry_if_exception_type((_LLMRateLimitError, _LLMTransientError)),
    wait=wait_exponential(multiplier=1, min=2, max=30),
    stop=stop_after_attempt(4),
    before_sleep=before_sleep_log(logger, logging.DEBUG),
    reraise=False,
)
async def _call_anthropic(
    prompt: str,
    model_id: str,
    api_key: str,
    system: str,
    max_tokens: int = 2500,
    temperature: float = 0.1,
) -> Optional[str]:
    from anthropic import AsyncAnthropic

    client = AsyncAnthropic(api_key=api_key)
    try:
        resp = await client.messages.create(
            model=model_id,
            max_tokens=max_tokens,
            temperature=temperature,
            system=system,
            messages=[{"role": "user", "content": prompt}],
        )
        return resp.content[0].text if resp.content else None
    except Exception as exc:
        msg = str(exc).lower()
        if "529" in msg or "overloaded" in msg or "rate" in msg:
            raise _LLMRateLimitError(str(exc)) from exc
        if any(c in msg for c in ("500", "502", "503", "504", "timeout")):
            raise _LLMTransientError(str(exc)) from exc
        logger.debug("Anthropic call failed: %s", exc)
        return None
    finally:
        await client.close()


def _build_cleaning_prompt(doc: dict, instructions: str, output_schema: dict) -> str:
    text = doc.get("text", "")
    title = doc.get("title", "")
    url = doc.get("url", "")
    source_type = doc.get("source_type", "")
    platform = doc.get("platform", "")

    max_text_chars = 16000
    text_snippet = text[:max_text_chars] + ("..." if len(text) > max_text_chars else "")

    schema_json = json.dumps(output_schema, indent=2)
    content_types_str = ", ".join(_CONTENT_TYPES)

    prompt = f"""Analyse this research document and extract structured information.

RESEARCH GOAL / CLEANING INSTRUCTIONS:
{instructions}

DOCUMENT METADATA:
- Title: {title}
- URL: {url}
- Source type: {source_type}
- Platform: {platform}

DOCUMENT CONTENT:
{text_snippet}

OUTPUT SCHEMA (extract these fields):
{schema_json}

ADDITIONAL REQUIRED FIELDS (always include):
- content_type: one of [{content_types_str}]
- relevance_score: float 0.0-1.0 (how relevant to the research goal)
- relevance_reasoning: one sentence explaining WHY this score was given (e.g. "Directly reports empirical findings on X" or "Only tangentially mentions X in passing")
- is_relevant: bool (true if relevance_score >= 0.5)
- summary: 2-4 sentence summary of the document's main findings

INSTRUCTIONS:
1. Classify the content_type from the list above
2. Score relevance 0.0-1.0 against the research goal/instructions
3. Write ONE sentence explaining the relevance score in relevance_reasoning
4. Extract all fields from the output schema (use null for missing fields)
5. Write a concise summary

Respond with a single valid JSON object containing all schema fields plus content_type, relevance_score, relevance_reasoning, is_relevant, and summary."""

    return prompt


def _parse_llm_json(text: str) -> Optional[dict]:
    if not text:
        return None

    text = text.strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    match = re.search(r"```(?:json)?\s*([\s\S]*?)```", text, re.IGNORECASE)
    if match:
        try:
            return json.loads(match.group(1).strip())
        except json.JSONDecodeError:
            pass

    match = re.search(r"\{[\s\S]+\}", text)
    if match:
        try:
            return json.loads(match.group(0))
        except json.JSONDecodeError:
            pass

    logger.debug("LLMCleaner: failed to parse JSON from response: %s...", text[:200])
    return None


def _merge_doc_with_extraction(doc: dict, extracted: dict, output_schema: dict) -> dict:
    result = dict(doc)

    # System fields are computed with explicit defaults and must not be
    # overwritten by the generic schema loop below (which may carry None values).
    _SYSTEM_FIELDS = {"content_type", "relevance_score", "relevance_reasoning", "is_relevant", "summary"}

    result["content_type"] = extracted.get("content_type", "unknown")
    _score = extracted.get("relevance_score")
    result["relevance_score"] = float(_score if _score is not None else 0.5)
    result["relevance_reasoning"] = extracted.get("relevance_reasoning", "")
    result["is_relevant"] = bool(extracted.get("is_relevant", result["relevance_score"] >= 0.5))
    result["summary"] = extracted.get("summary", "")

    for key in output_schema:
        if key in _SYSTEM_FIELDS:
            continue  # already set above with proper defaults
        if key in extracted:
            result[key] = extracted[key]
        elif key not in result:
            result[key] = _default_for_schema_type(output_schema[key])

    if not result.get("title") and extracted.get("title"):
        result["title"] = extracted["title"]

    result["cleaned"] = True
    return result


def _default_for_schema_type(type_hint: Any) -> Any:
    """Return a sensible default for a schema type hint."""
    if isinstance(type_hint, str):
        hint = type_hint.lower()
        if hint == "bool":
            return False
        if hint == "float":
            return 0.0
        if hint == "int":
            return 0
        if hint == "list":
            return []
        if hint == "dict":
            return {}
        return None
    if isinstance(type_hint, dict):
        return {}
    return None


def _fallback_clean(doc: dict, output_schema: dict) -> dict:
    """Return a basic cleaned doc when LLM is unavailable.

    Documents are marked not relevant (score=0.0, is_relevant=False) and
    flagged with a quality_warning so callers know scoring did not run.
    """
    result = dict(doc)
    result["content_type"] = "unknown"
    result["relevance_score"] = 0.0
    result["is_relevant"] = False
    result["summary"] = doc.get("text", "")[:300]
    result["cleaned"] = False
    result["quality_warning"] = "LLM unavailable — document not scored"

    for key, type_hint in output_schema.items():
        if key not in result:
            result[key] = _default_for_schema_type(type_hint)

    return result


