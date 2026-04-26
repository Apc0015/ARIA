"""Research Director conversation endpoints.

Session lifecycle:
  POST /api/director/session          — start conversation, returns first question
  POST /api/director/{id}/answer      — submit answer, returns next question or done+brief
  GET  /api/director/{id}             — get current session state
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any
from uuid import uuid4

from fastapi import APIRouter, HTTPException

logger = logging.getLogger("aria")

router = APIRouter()

# In-memory session store (process lifetime; good enough for this use-case)
_sessions: dict[str, "_Session"] = {}


class _Session:
    """Holds an active Research Director conversation."""

    def __init__(self, topic: str, session_id: str) -> None:
        self.session_id = session_id
        self.topic = topic
        self.done = False
        self.brief: dict[str, Any] | None = None
        self._gen: Any = None                   # AsyncGenerator
        self._pending_question: dict | None = None
        self._answer_queue: asyncio.Queue[str] = asyncio.Queue(maxsize=1)
        self._task: asyncio.Task | None = None

    def start(self) -> None:
        """Kick off the generator as a background task."""
        self._task = asyncio.create_task(self._drive())

    async def _drive(self) -> None:
        """Run the full conversation, parking at each question."""
        try:
            from aria.engine.intelligence.research_director import ResearchDirector
            director = ResearchDirector()
            gen = director.run_conversation(self.topic)
            event = await gen.asend(None)

            while event.get("type") != "done":
                self._pending_question = event
                # Wait for frontend answer
                answer = await self._answer_queue.get()
                self._pending_question = None
                try:
                    event = await gen.asend(answer)
                except StopAsyncIteration:
                    break

            # Conversation done — build brief dict
            brief_obj = event.get("brief")
            if brief_obj is not None:
                # Generate phased plan
                try:
                    from aria.engine.intelligence.phased_planner import build_phases
                    phases = build_phases(brief_obj)
                    brief_obj.phases = phases
                except Exception as exc:
                    logger.warning("Phase planning failed: %s", exc)
                self.brief = brief_obj.to_dict()
            self.done = True

        except Exception as exc:
            logger.warning("Director session %s failed: %s", self.session_id, exc)
            self.done = True
            self._pending_question = None

    async def wait_for_question(self, timeout: float = 30.0) -> dict | None:
        """Wait until a question is ready or conversation is done."""
        deadline = asyncio.get_event_loop().time() + timeout
        while True:
            if self._pending_question is not None:
                return self._pending_question
            if self.done:
                return None
            if asyncio.get_event_loop().time() > deadline:
                return None
            await asyncio.sleep(0.05)

    async def submit_answer(self, answer: str) -> None:
        await self._answer_queue.put(answer)


# ── Endpoints ──────────────────────────────────────────────────────────────────

@router.post("/api/director/session")
async def start_session(payload: dict) -> dict:
    """Start a Research Director conversation.

    Body: {"topic": "depression"}
    Returns: {"session_id": "...", "question": {...} | null, "done": bool}
    """
    topic = (payload.get("topic") or "").strip()
    if not topic:
        raise HTTPException(status_code=422, detail="topic is required")

    session_id = uuid4().hex[:12]
    session = _Session(topic, session_id)
    _sessions[session_id] = session
    session.start()

    # Wait for first question (or immediate done if topic is unambiguous + no LLM)
    question = await session.wait_for_question(timeout=30.0)

    return {
        "session_id": session_id,
        "done": session.done,
        "question": question,
        "brief": session.brief if session.done else None,
    }


@router.post("/api/director/{session_id}/answer")
async def submit_answer(session_id: str, payload: dict) -> dict:
    """Submit an answer for the current question.

    Body: {"answer": "mental health"} or {"answer": "skip"}
    Returns: {"done": bool, "question": {...} | null, "brief": {...} | null}
    """
    session = _sessions.get(session_id)
    if session is None:
        raise HTTPException(status_code=404, detail=f"Session '{session_id}' not found")
    if session.done:
        return {"done": True, "question": None, "brief": session.brief}

    answer = str(payload.get("answer") or "skip").strip()
    await session.submit_answer(answer)

    # Wait for next question or done
    question = await session.wait_for_question(timeout=30.0)

    return {
        "done": session.done,
        "question": question,
        "brief": session.brief if session.done else None,
    }


@router.get("/api/director/{session_id}")
async def get_session(session_id: str) -> dict:
    """Get current session state."""
    session = _sessions.get(session_id)
    if session is None:
        raise HTTPException(status_code=404, detail=f"Session '{session_id}' not found")
    return {
        "session_id": session_id,
        "done": session.done,
        "question": session._pending_question,
        "brief": session.brief if session.done else None,
    }


@router.delete("/api/director/{session_id}")
async def close_session(session_id: str) -> dict:
    """Close and clean up a session."""
    session = _sessions.pop(session_id, None)
    if session and session._task and not session._task.done():
        session._task.cancel()
    return {"closed": True}
