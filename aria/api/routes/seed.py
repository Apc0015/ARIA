"""Seed paper API routes.

GET  /api/seed/resolve?q=<doi_or_url>   — resolve DOI or URL → paper preview
POST /api/seed/upload                   — upload PDF → extract text + paper preview
POST /api/runs/with-pdf                 — start a run with an uploaded PDF as seed
"""

from __future__ import annotations

import asyncio
import io
import logging
import re
import tempfile
import os
from typing import Optional

from fastapi import APIRouter, HTTPException, Query, UploadFile, File, Form, Request
from pydantic import BaseModel

logger = logging.getLogger("aria")

router = APIRouter(tags=["seed"])


# ---------------------------------------------------------------------------
# Response schema
# ---------------------------------------------------------------------------

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


# ---------------------------------------------------------------------------
# GET /api/seed/resolve
# ---------------------------------------------------------------------------

@router.get("/api/seed/resolve", response_model=SeedPreview)
async def resolve_seed(q: str = Query(..., description="DOI or URL to resolve")):
    """Resolve a DOI or URL to paper metadata for preview before launching a run."""
    q = q.strip()
    if not q:
        raise HTTPException(status_code=400, detail="q is required")

    # Determine if it's a DOI or URL
    is_url = q.startswith("http")
    doi = ""
    url = q if is_url else ""

    if not is_url:
        # Extract DOI if it looks like one (may or may not start with 10.)
        doi_match = re.search(r'10\.\d{4,9}/\S+', q)
        if doi_match:
            doi = doi_match.group(0).rstrip('.,)')
        else:
            doi = q

    try:
        from aria.engine.citation.seed import SeedFetcher
        fetcher = SeedFetcher(timeout=15)
        result = await fetcher.fetch(doi=doi, url=url)
        rec = result.level0_record
        ref_count = len(result.raw_references) if result.raw_references else None
        return SeedPreview(
            title=rec.title or "",
            authors=rec.authors or [],
            year=rec.year or "",
            journal=rec.journal or "",
            doi=rec.doi or "",
            url=rec.url or url,
            abstract=rec.abstract or "",
            ref_count=ref_count,
            access_status=rec.access_status,
        )
    except Exception as exc:
        logger.warning("Seed resolve failed for %r: %s", q, exc)
        # Return a minimal preview so the UI doesn't break
        return SeedPreview(doi=doi, url=url)


# ---------------------------------------------------------------------------
# POST /api/seed/upload
# ---------------------------------------------------------------------------

@router.post("/api/seed/upload", response_model=SeedPreview)
async def upload_seed_pdf(file: UploadFile = File(...)):
    """Upload a PDF and extract paper metadata + reference count for preview."""
    if not file.filename or not file.filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Only PDF files are supported")

    content = await file.read()
    if len(content) > 50 * 1024 * 1024:  # 50 MB cap
        raise HTTPException(status_code=413, detail="PDF too large (max 50 MB)")

    try:
        title, authors, year, journal, doi, abstract, raw_refs = _extract_pdf_metadata(content)
        return SeedPreview(
            title=title,
            authors=authors,
            year=year,
            journal=journal,
            doi=doi,
            abstract=abstract,
            ref_count=len(raw_refs) if raw_refs else None,
            access_status="open_access",
        )
    except Exception as exc:
        logger.warning("PDF extraction failed: %s", exc)
        return SeedPreview(access_status="open_access")


# ---------------------------------------------------------------------------
# POST /api/runs/with-pdf  (start a run with an uploaded PDF seed)
# ---------------------------------------------------------------------------

@router.post("/api/runs/with-pdf")
async def start_run_with_pdf(
    request: Request,
    file: UploadFile = File(...),
    topic: str = Form(default=""),
    depth_level: int = Form(default=2),
    director_session_id: str = Form(default=""),
):
    """Start an ARIA run using an uploaded PDF as the seed paper."""
    content = await file.read()
    if len(content) > 50 * 1024 * 1024:
        raise HTTPException(status_code=413, detail="PDF too large (max 50 MB)")

    try:
        title, authors, year, journal, doi, abstract, raw_refs = _extract_pdf_metadata(content)
    except Exception as exc:
        raise HTTPException(status_code=422, detail=f"Could not extract PDF content: {exc}")

    # Write PDF to temp file for full-text storage
    tmp = tempfile.NamedTemporaryFile(suffix=".pdf", delete=False)
    tmp.write(content)
    tmp.close()

    # Build mission config with citation_crawl enabled
    resolved_topic = topic.strip() or title or "research"
    mission = {
        "collection": {
            "topic": resolved_topic,
            "intent": f"Literature review seeded from: {title}",
            "max_documents": 300,
        },
        "citation_crawl": {
            "enabled": True,
            "seed_pdf_path": tmp.name,
            "seed_doi": doi,
            "seed_title": title,
            "seed_raw_refs": raw_refs,
            "levels": 1,
            "resolve_abstracts": True,
            "fetch_open_access": True,
            "max_refs": 100,
        },
    }

    # Launch via run_manager
    run_manager = getattr(request.app.state, "run_manager", None)
    if run_manager is None:
        raise HTTPException(status_code=503, detail="Run manager not available")

    try:
        run = await run_manager.start_run(
            topic=resolved_topic,
            depth_level=depth_level,
            mission=mission,
            director_session_id=director_session_id or None,
        )
        return run
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))
    finally:
        try:
            os.unlink(tmp.name)
        except OSError:
            pass


# ---------------------------------------------------------------------------
# PDF extraction helper
# ---------------------------------------------------------------------------

def _extract_pdf_metadata(content: bytes) -> tuple:
    """Extract title, authors, year, journal, doi, abstract, raw_refs from PDF bytes.

    Returns:
        (title, authors, year, journal, doi, abstract, raw_refs)
    """
    text = _pdf_to_text(content)
    if not text:
        return "", [], "", "", "", "", []

    title = _extract_title(text)
    authors = _extract_authors(text)
    year = _extract_year(text)
    journal = _extract_journal(text)
    doi = _extract_doi(text)
    abstract = _extract_abstract(text)
    raw_refs = _extract_refs(text)

    return title, authors, year, journal, doi, abstract, raw_refs


def _pdf_to_text(content: bytes) -> str:
    """Convert PDF bytes to plain text. Tries PyMuPDF first, falls back to pypdf."""
    # Try PyMuPDF (fitz) — best quality
    try:
        import fitz  # type: ignore
        doc = fitz.open(stream=content, filetype="pdf")
        pages = [page.get_text() for page in doc]
        doc.close()
        return "\n".join(pages)
    except ImportError:
        pass
    except Exception:
        pass

    # Try pypdf
    try:
        import pypdf  # type: ignore
        reader = pypdf.PdfReader(io.BytesIO(content))
        pages = []
        for page in reader.pages:
            try:
                pages.append(page.extract_text() or "")
            except Exception:
                pass
        return "\n".join(pages)
    except ImportError:
        pass
    except Exception:
        pass

    # Try pdfminer
    try:
        from pdfminer.high_level import extract_text as pdfminer_extract  # type: ignore
        return pdfminer_extract(io.BytesIO(content))
    except ImportError:
        pass
    except Exception:
        pass

    return ""


def _extract_title(text: str) -> str:
    lines = [l.strip() for l in text.splitlines() if l.strip()]
    # Title is usually one of the first few non-trivial lines
    for line in lines[:10]:
        if len(line) > 20 and not re.match(r'^(Abstract|Introduction|doi|http|www|©)', line, re.IGNORECASE):
            return line[:300]
    return lines[0][:300] if lines else ""


def _extract_authors(text: str) -> list[str]:
    lines = [l.strip() for l in text.splitlines() if l.strip()]
    # Look for author line — typically after title, before abstract
    # Heuristic: line with multiple names separated by commas or &
    for line in lines[1:15]:
        if re.search(r'[A-Z][a-z]+,?\s+[A-Z]\.', line) and len(line) < 300:
            parts = re.split(r'[,;&]|\band\b', line)
            authors = [p.strip().rstrip(',.') for p in parts if len(p.strip()) > 3]
            if 1 < len(authors) <= 15:
                return authors[:10]
    return []


def _extract_year(text: str) -> str:
    m = re.search(r'\b(20\d{2}|19\d{2})\b', text[:2000])
    return m.group(1) if m else ""


def _extract_journal(text: str) -> str:
    # Look for journal patterns near the top
    patterns = [
        r'(?:Journal of|Review of|Proceedings of|Annals of|Bulletin of)\s+[A-Z][^\n]{5,60}',
        r'[A-Z][a-z]+ (?:Journal|Review|Letters|Transactions|Proceedings|Studies)[^\n]{0,50}',
    ]
    for pat in patterns:
        m = re.search(pat, text[:3000])
        if m:
            return m.group(0).strip()[:100]
    return ""


def _extract_doi(text: str) -> str:
    m = re.search(r'10\.\d{4,9}/[^\s<>"\']+', text[:5000])
    if m:
        return m.group(0).rstrip('.,)')
    return ""


def _extract_abstract(text: str) -> str:
    for marker in ['Abstract', 'ABSTRACT', 'Summary', 'SUMMARY']:
        idx = text.find(marker)
        if idx != -1:
            snippet = text[idx + len(marker):idx + 2500]
            snippet = re.split(r'\n\n|(?:Introduction|INTRODUCTION|Keywords|KEYWORDS)', snippet)[0]
            abstract = snippet.strip().lstrip(':').strip()
            if len(abstract) > 50:
                return abstract[:2000]
    return ""


def _extract_refs(text: str) -> list[str]:
    """Extract raw reference strings from PDF text."""
    from aria.engine.citation.ref_parser import ReferenceParser
    parser = ReferenceParser()

    # Find references section
    for marker in ['References\n', 'REFERENCES\n', 'Bibliography\n', 'BIBLIOGRAPHY\n']:
        idx = text.find(marker)
        if idx != -1:
            ref_block = text[idx + len(marker):]
            records = parser.parse_text_block(ref_block)
            return [r.get("raw", "") for r in records if r.get("raw")]

    return []
