"""ARIA 5.0 — domain and country discovery endpoints."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

router = APIRouter(prefix="/api/domains", tags=["domains"])


class AnalyzeRequest(BaseModel):
    query: str
    domains: list[str] | None = None
    countries: list[str] | None = None


@router.get("")
async def list_domains():
    """List all available research domains."""
    from aria.engine.domains.registry import DOMAINS
    return {
        "domains": [
            {
                "id": d.id,
                "label": d.label,
                "description": d.description,
                "icon": d.icon,
                "collectors": d.collectors,
                "data_types": d.data_types,
                "country_aware": d.country_aware,
                "citation_depth": d.citation_depth,
            }
            for d in DOMAINS.values()
        ],
        "total": len(DOMAINS),
    }


@router.get("/countries")
async def list_countries():
    """List all supported countries and regions."""
    from aria.engine.domains.countries import COUNTRIES, REGIONS
    return {
        "countries": [
            {
                "code": c.code,
                "name": c.name,
                "flag": c.flag,
                "region": c.region,
                "gov_domain": c.gov_domain,
                "language": c.language,
            }
            for c in COUNTRIES.values()
        ],
        "regions": {
            region: codes for region, codes in REGIONS.items()
        },
        "total": len(COUNTRIES),
    }


@router.post("/analyze")
async def analyze_query(request: AnalyzeRequest):
    """Analyze a natural language query → structured intent + collection plan."""
    try:
        from aria.engine.domains.planner import build_collection_plan
        plan = await build_collection_plan(
            query=request.query,
            domains=request.domains,
            countries=request.countries,
        )
        return {
            "intent": {
                "topic": plan.intent.topic,
                "domains": plan.intent.domains,
                "countries": plan.intent.countries,
                "data_types": plan.intent.data_types,
                "time_range": plan.intent.time_range,
                "confidence": plan.intent.confidence,
                "pending_questions": plan.intent.pending_questions,
                "ready": plan.intent.ready,
            },
            "plan": {
                "active_collectors": plan.active_collectors,
                "queries": plan.queries[:10],  # preview only
                "query_count": len(plan.queries),
                "citation_depth": plan.citation_depth,
                "depth_level": plan.depth_level,
                "estimated_docs": plan.estimated_docs,
                "summary": plan.summary,
            },
        }
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@router.get("/{domain_id}/collectors")
async def domain_collectors(domain_id: str):
    """Get the collectors activated for a specific domain."""
    from aria.engine.domains.registry import DOMAINS
    domain = DOMAINS.get(domain_id)
    if not domain:
        raise HTTPException(status_code=404, detail=f"Domain '{domain_id}' not found")
    return {
        "domain": domain_id,
        "collectors": domain.collectors,
        "always_include": domain.always_include,
        "query_modifiers": domain.query_modifiers,
    }
