"""
Streaming pipeline — clean documents as they arrive from collectors.

Instead of: collect ALL → batch clean ALL
Does:       each doc arrives → clean immediately (with concurrency cap)

Useful for:
  - Real-time progress to frontend (clean docs available faster)
  - Lower peak memory (don't hold all raw docs before cleaning)
  - Better throughput (cleaning overlaps with ongoing collection)

Usage:
    pipeline = StreamingPipeline(cleaner, event_callback=emit_fn)
    async with pipeline.context() as stream:
        for task in collector_tasks:
            await stream.submit_batch(await task)
    clean_docs = stream.results()
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any, Callable, Optional

logger = logging.getLogger("aria")


class StreamingPipeline:
    """
    Wraps LLMCleaner with a bounded async queue for streaming clean.

    Each doc submitted is cleaned as soon as a worker slot is free.
    Concurrency = max_concurrent_cleans (default: 3, respects rate limits).
    """

    def __init__(
        self,
        cleaner: Any,
        instructions: str = "Extract key information.",
        output_schema: Optional[dict] = None,
        max_concurrent: int = 3,
        event_callback: Optional[Callable] = None,
    ) -> None:
        self._cleaner = cleaner
        self._instructions = instructions
        self._schema = output_schema or {}
        self._max_concurrent = max_concurrent
        self._emit = event_callback

        self._queue: asyncio.Queue[Optional[dict]] = asyncio.Queue(maxsize=200)
        self._results: list[dict] = []
        self._clean_count = 0
        self._worker_task: Optional[asyncio.Task] = None
        self._sem = asyncio.Semaphore(max_concurrent)

    async def __aenter__(self) -> "StreamingPipeline":
        self._worker_task = asyncio.create_task(self._worker())
        return self

    async def __aexit__(self, *args: Any) -> None:
        # Signal workers to stop
        await self._queue.put(None)
        if self._worker_task:
            try:
                await asyncio.wait_for(self._worker_task, timeout=300)
            except asyncio.TimeoutError:
                self._worker_task.cancel()
                logger.warning("Streaming pipeline worker timed out")

    async def submit(self, doc: dict) -> None:
        """Submit a single document for cleaning."""
        await self._queue.put(doc)

    async def submit_batch(self, docs: list[dict]) -> None:
        """Submit a batch of documents."""
        for doc in docs:
            await self._queue.put(doc)

    def results(self) -> list[dict]:
        """Return all cleaned documents collected so far."""
        return list(self._results)

    async def _worker(self) -> None:
        """Drain queue, clean each doc with bounded concurrency."""
        pending: set[asyncio.Task] = set()

        while True:
            try:
                doc = await asyncio.wait_for(self._queue.get(), timeout=2.0)
            except asyncio.TimeoutError:
                # Check if any pending tasks done
                if pending:
                    done, pending = await asyncio.wait(pending, timeout=0.1)
                    for t in done:
                        result = t.result()
                        if result:
                            self._results.append(result)
                            self._clean_count += 1
                continue

            if doc is None:
                # Drain remaining queue
                while not self._queue.empty():
                    item = self._queue.get_nowait()
                    if item is not None:
                        task = asyncio.create_task(self._clean_one(item))
                        pending.add(task)
                break

            task = asyncio.create_task(self._clean_one(doc))
            pending.add(task)
            self._queue.task_done()

            # Reap completed
            if len(pending) >= self._max_concurrent * 2:
                done, pending = await asyncio.wait(pending, return_when=asyncio.FIRST_COMPLETED)
                for t in done:
                    try:
                        result = t.result()
                        if result:
                            self._results.append(result)
                            self._clean_count += 1
                    except Exception as exc:
                        logger.debug("Streaming clean task error: %s", exc)

        # Wait for all remaining tasks
        if pending:
            done_all = await asyncio.gather(*pending, return_exceptions=True)
            for result in done_all:
                if isinstance(result, dict):
                    self._results.append(result)
                    self._clean_count += 1

        logger.info("Streaming pipeline complete: %d docs cleaned", self._clean_count)

    async def _clean_one(self, doc: dict) -> Optional[dict]:
        """Clean a single document with semaphore-bounded concurrency."""
        async with self._sem:
            try:
                cleaned = await self._cleaner.clean_one(doc, self._instructions, self._schema)
                if cleaned and self._emit:
                    try:
                        coro = self._emit("stream_clean", f"Cleaned: {doc.get('title', '')[:60]}")
                        if asyncio.iscoroutine(coro):
                            await coro
                    except Exception:
                        pass
                return cleaned
            except Exception as exc:
                logger.debug("Streaming clean error for %s: %s", doc.get("url", "")[:60], exc)
                return doc  # return raw on clean failure


# ─── Batch streaming (simpler alternative) ────────────────────────────────────

async def stream_clean_as_collected(
    collector_tasks: list[asyncio.Task],
    cleaner: Any,
    instructions: str,
    output_schema: dict,
    event_callback: Optional[Callable] = None,
    max_concurrent_clean: int = 3,
) -> tuple[list[dict], list[dict]]:
    """
    Run collectors in parallel, clean each batch as it completes.

    Returns:
        (raw_docs, clean_docs) — both lists in collection order
    """
    raw_all: list[dict] = []
    clean_all: list[dict] = []
    sem = asyncio.Semaphore(max_concurrent_clean)

    async def clean_batch_bounded(batch: list[dict]) -> list[dict]:
        async with sem:
            try:
                return await cleaner.clean_batch(batch, instructions, output_schema)
            except Exception as exc:
                logger.warning("Streaming batch clean failed: %s", exc)
                return batch  # return raw on failure

    # As each collector completes, clean its batch immediately
    clean_tasks: list[asyncio.Task] = []
    raw_batches: list[list[dict]] = []

    for coro_task in asyncio.as_completed(collector_tasks):
        try:
            batch = await coro_task
            if batch:
                raw_batches.append(batch)
                raw_all.extend(batch)
                # Start cleaning this batch immediately
                t = asyncio.create_task(clean_batch_bounded(batch))
                clean_tasks.append(t)
        except Exception as exc:
            logger.debug("Collector task failed: %s", exc)

    # Await all cleaning tasks
    clean_results = await asyncio.gather(*clean_tasks, return_exceptions=True)
    for result in clean_results:
        if isinstance(result, list):
            clean_all.extend(result)
        elif isinstance(result, Exception):
            logger.debug("Clean task error: %s", result)

    return raw_all, clean_all
