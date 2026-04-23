"""ARIA 5.0 — intent agent streaming chat endpoint."""

from __future__ import annotations

import json
from typing import AsyncGenerator

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

router = APIRouter(prefix="/api/chat", tags=["chat"])


class ChatMessage(BaseModel):
    message: str
    intent_state: dict | None = None  # serialised IntentResult for multi-turn


class ClarifyRequest(BaseModel):
    answer: str
    intent_state: dict


@router.post("/analyze")
async def analyze(request: ChatMessage):
    """Parse a natural language query → intent result.

    Returns the intent JSON and any clarifying questions to ask the user.
    """
    try:
        from aria.engine.domains.planner import IntentAgent
        agent = IntentAgent()
        intent = await agent.analyze(request.message)
        return {
            "topic": intent.topic,
            "domains": intent.domains,
            "countries": intent.countries,
            "data_types": intent.data_types,
            "time_range": intent.time_range,
            "confidence": intent.confidence,
            "pending_questions": intent.pending_questions,
            "ready": intent.ready,
        }
    except ImportError:
        raise HTTPException(status_code=503, detail="Intent agent unavailable (engine not installed)")
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Analysis failed: {type(exc).__name__}")


@router.post("/clarify")
async def clarify(request: ClarifyRequest):
    """Refine intent with user's answer to a clarifying question."""
    try:
        from aria.engine.domains.planner import IntentAgent, IntentResult
        agent = IntentAgent()

        # Reconstruct IntentResult from serialised state
        state = request.intent_state
        intent = IntentResult(
            original_query=state.get("original_query", ""),
            topic=state.get("topic", ""),
            domains=state.get("domains", []),
            countries=state.get("countries", ["GLOBAL"]),
            data_types=state.get("data_types", []),
            time_range=state.get("time_range"),
            confidence=state.get("confidence", {}),
            pending_questions=state.get("pending_questions", []),
            ready=state.get("ready", False),
        )

        updated = await agent.clarify(intent, request.answer)
        return {
            "topic": updated.topic,
            "domains": updated.domains,
            "countries": updated.countries,
            "data_types": updated.data_types,
            "time_range": updated.time_range,
            "confidence": updated.confidence,
            "pending_questions": updated.pending_questions,
            "ready": updated.ready,
        }
    except ImportError:
        raise HTTPException(status_code=503, detail="Intent agent unavailable (engine not installed)")
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Clarification failed: {type(exc).__name__}")


@router.post("/plan")
async def build_plan(request: ChatMessage):
    """Build a full collection plan from a query (or refined intent_state)."""
    from aria.engine.domains.planner import (
        IntentAgent, IntentResult, StrategyPlanner
    )
    from aria.engine.domains.registry import DOMAINS

    if request.intent_state:
        state = request.intent_state
        intent = IntentResult(
            original_query=state.get("original_query", request.message),
            topic=state.get("topic", request.message[:60]),
            domains=state.get("domains", []),
            countries=state.get("countries", ["GLOBAL"]),
            data_types=state.get("data_types", []),
            time_range=state.get("time_range"),
            confidence=state.get("confidence", {}),
            pending_questions=[],
            ready=True,
        )
    else:
        agent = IntentAgent()
        intent = await agent.analyze(request.message)
        intent.ready = True

    planner = StrategyPlanner()
    plan = await planner.build_plan(intent)

    return {
        "intent": {
            "topic": plan.intent.topic,
            "domains": plan.intent.domains,
            "countries": plan.intent.countries,
        },
        "active_collectors": plan.active_collectors,
        "queries": plan.queries,
        "query_count": len(plan.queries),
        "citation_depth": plan.citation_depth,
        "depth_level": plan.depth_level,
        "estimated_docs": plan.estimated_docs,
        "summary": plan.summary,
    }
