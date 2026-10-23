"""Seed paper preview for citation-crawl runs.

GET /api/seed/resolve resolves a DOI or URL to paper metadata so the
Launch page can show what will be crawled before a run starts.
"""

from __future__ import annotations

import logging
import re
from typing import Optional

from fastapi import APIRouter, HTTPException, Query, Request
from pydantic import BaseModel

from aria.api.authorization import require_role
from aria.utils.scrub import scrub_secrets
from aria.utils.url import is_safe_public_http_url

logger = logging.getLogger("aria")

router = APIRouter(tags=["seed"])

_DOI_RE = re.compile(r"10\.\d{4,9}/\S+")


class SeedPreview(BaseModel):
    title: str = ""
    authors: list[str] = []
    year: str = ""
    journal: str = ""
    doi: str = ""
    url: str = ""
    abstract: str = ""
    ref_count: Optional[int] = None
    access_status: str = "unknown"


def parse_seed_input(q: str) -> tuple[str, str]:
    """Split user input into (doi, url). Raises ValueError when unusable."""
    q = q.strip()
    if not q:
        raise ValueError("Enter a DOI or a paper URL")
    if q.lower().startswith(("http://", "https://")):
        if not is_safe_public_http_url(q):
            raise ValueError("Seed URL must be a public http(s) address")
        return "", q
    match = _DOI_RE.search(q)
    if not match:
        raise ValueError("Not a recognisable DOI (expected 10.xxxx/...)")
    return match.group(0).rstrip(".,)"), ""


@router.get("/api/seed/resolve", response_model=SeedPreview)
async def resolve_seed(request: Request, q: str = Query(..., max_length=2048)):
    """Resolve a DOI or URL to paper metadata for preview before launching a run."""
    require_role(request, "admin", "member")
    try:
        doi, url = parse_seed_input(q)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))

    try:
        from aria.engine.citation.seed import SeedFetcher

        result = await SeedFetcher(timeout=15).fetch(doi=doi, url=url)
        rec = result.level0_record
        return SeedPreview(
            title=rec.title or "",
            authors=rec.authors or [],
            year=rec.year or "",
            journal=rec.journal or "",
            doi=rec.doi or doi,
            url=rec.url or url,
            abstract=rec.abstract or "",
            ref_count=len(result.raw_references) if result.raw_references else None,
            access_status=rec.access_status,
        )
    except Exception as exc:
        logger.warning("Seed resolve failed: %s", scrub_secrets(str(exc)))
        # A minimal preview keeps the launch flow usable when metadata lookup fails.
        return SeedPreview(doi=doi, url=url)
