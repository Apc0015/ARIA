"""Citation crawl phase — runs before normal collection when a mission has a seed paper.

When a mission YAML contains a ``citation_crawl`` block, this phase:

1. Fetches the seed paper (Level 0) — full text + metadata + reference list
2. Parses all references from the seed paper
3. Resolves metadata + abstracts for each Level 1 reference via CrossRef /
   Semantic Scholar / arXiv / PubMed (open access only)
4. Fetches full text for any open-access Level 1 papers
5. Saves full texts to ``{output_dir}/full-texts/``
6. Returns a list of CorpusRecord objects (Level 0 + all Level 1)

The phase emits progress events via ``emit_fn`` compatible with ARIA's
existing SSE stream contract.

Mission YAML schema::

    citation_crawl:
      enabled: true
      seed_doi: "10.5787/52-3-1483"
      seed_url: "https://scielo.org.za/scielo.php?script=sci_arttext&pid=S2224-00202024000300005"
      levels: 1                    # only 1 supported right now (Level 0 + Level 1)
      resolve_abstracts: true      # attempt CrossRef/S2 metadata for Level 1
      fetch_open_access: true      # attempt full-text for open-access Level 1 papers
      max_refs: 100                # cap on Level 1 papers to process
      output_subdir: "citation-graph"  # subdirectory under run output dir
"""

from __future__ import annotations

import asyncio
import logging
import os
import re
from datetime import datetime, timezone
from typing import Any, Callable, Optional

# Issue #10 fix — lazy import httpx so a missing install only breaks
# citation_crawl at call time, not at module import time
try:
    import httpx as _httpx
except ImportError:  # pragma: no cover
    _httpx = None  # type: ignore[assignment]

from aria.engine.citation.ref_parser import ReferenceParser, RefRecord
from aria.engine.citation.seed import CorpusRecord, SeedFetcher, SeedResult

logger = logging.getLogger("aria")

# ---------------------------------------------------------------------------
# Config helpers
# ---------------------------------------------------------------------------

def _get_citation_crawl_config(mission_config: Any) -> dict:
    """Extract citation_crawl section from mission config (dict or object)."""
    if isinstance(mission_config, dict):
        return mission_config.get("citation_crawl") or {}
    return getattr(mission_config, "citation_crawl", None) or {}


def citation_crawl_enabled(mission_config: Any) -> bool:
    """Return True if the mission has an enabled citation_crawl block."""
    cfg = _get_citation_crawl_config(mission_config)
    if not cfg:
        return False
    return bool(cfg.get("enabled", True) and (cfg.get("seed_doi") or cfg.get("seed_url")))


# ---------------------------------------------------------------------------
# Metadata resolution for Level 1
# ---------------------------------------------------------------------------

_CROSSREF_WORKS = "https://api.crossref.org/works"
_S2_SEARCH = "https://api.semanticscholar.org/graph/v1/paper/search"
_ARXIV_API = "https://export.arxiv.org/api/query"
_PUBMED_SEARCH = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi"
_PUBMED_SUMMARY = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esummary.fcgi"

# Issue #7 fix — defaults still here but overridable via mission YAML
_DEFAULT_SEMAPHORE_LIMIT = 5
_DEFAULT_REQUEST_DELAY = 0.25  # seconds between requests


def _crossref_mailto() -> dict[str, str]:
    """Crossref polite-pool contact, sent only when one is configured."""
    email = os.getenv("UNPAYWALL_EMAIL", "")
    return {"mailto": email} if email else {}


async def _resolve_level1_metadata(
    ref: RefRecord,
    semaphore: asyncio.Semaphore,
    request_delay: float = _DEFAULT_REQUEST_DELAY,
) -> CorpusRecord:
    """Resolve metadata for a single Level 1 reference."""
    rec = CorpusRecord(
        level=1,
        title=ref.get("title", ""),
        authors=ref.get("authors", []) or _split_authors_raw(ref.get("authors_raw", "")),
        year=ref.get("year", ""),
        journal=ref.get("journal", ""),
        volume=ref.get("volume", ""),
        issue=ref.get("issue", ""),
        pages=ref.get("pages", ""),
        url=ref.get("url", ""),
        doi=ref.get("doi", ""),
        ref_type=ref.get("ref_type", "unknown"),
        raw_ref=ref.get("raw", ""),
        parse_notes=list(ref.get("parse_notes") or []),
    )

    title = rec.title.strip()
    year = rec.year

    # Web reports and grey literature — mark open access, no DOI resolution needed
    if rec.ref_type in ("web_report",) and rec.url:
        rec.doi_status = "not_applicable"
        rec.access_status = "open_access"
        return rec

    # For academic content attempt resolution
    if title and len(title) > 15:
        async with semaphore:
            await asyncio.sleep(request_delay)
            cr = await _crossref_title_search(title, year)
            if cr:
                _apply_crossref(rec, cr)
            else:
                await asyncio.sleep(request_delay)
                ss = await _semantic_scholar_search(title, year)
                if ss:
                    _apply_semantic_scholar(rec, ss)

    if not rec.doi:
        rec.doi_status = "not_found"
    elif rec.doi_status == "unknown":
        rec.doi_status = "unverified"

    # Determine access status
    if rec.access_status == "unknown":
        rec.access_status = _guess_access_status(rec)

    return rec


def _split_authors_raw(raw: str) -> list[str]:
    if not raw:
        return []
    raw = re.sub(r'\s+and\s+', ' & ', raw, flags=re.IGNORECASE)
    return [p.strip().rstrip('.,') for p in raw.split('&') if p.strip()]


async def _crossref_title_search(title: str, year: str) -> Optional[dict]:
    try:
        async with _httpx.AsyncClient(timeout=12) as client:
            resp = await client.get(
                _CROSSREF_WORKS,
                params={
                    "query.title": title[:120],
                    "rows": 3,
                    **_crossref_mailto(),
                },
            )
            if resp.status_code != 200:
                return None
            items = resp.json().get("message", {}).get("items", [])
            for item in items:
                item_year = _crossref_year(item)
                if year and item_year and abs(int(re.sub(r'[a-z]', '', year)) - int(item_year)) > 2:
                    continue
                return item
    except Exception as exc:
        logger.debug("CrossRef search error: %s", exc)
    return None


def _crossref_year(item: dict) -> str:
    for k in ("published-print", "published-online", "issued"):
        parts = item.get(k, {}).get("date-parts", [[]])
        if parts and parts[0]:
            return str(parts[0][0])
    return ""


def _apply_crossref(rec: CorpusRecord, item: dict) -> None:
    rec.doi = item.get("DOI", rec.doi)
    rec.doi_status = "verified" if rec.doi else rec.doi_status
    titles = item.get("title", [])
    if titles and not rec.title:
        rec.title = titles[0]
    containers = item.get("container-title", [])
    if containers and not rec.journal:
        rec.journal = containers[0]
    if not rec.volume:
        rec.volume = item.get("volume", "")
    if not rec.issue:
        rec.issue = item.get("issue", "")
    if not rec.pages:
        rec.pages = item.get("page", "")
    if not rec.year:
        rec.year = _crossref_year(item)
    abstract = item.get("abstract", "") or ""
    rec.abstract = re.sub(r"<[^>]+>", "", abstract).strip()
    links = item.get("link", [])
    if links and not rec.url:
        rec.url = links[0].get("URL", "")
    # Check open access
    oa = item.get("is-referenced-by-count")  # not OA flag but useful signal
    license_info = item.get("license", [])
    if license_info:
        rec.access_status = "open_access"


async def _semantic_scholar_search(title: str, year: str) -> Optional[dict]:
    try:
        async with _httpx.AsyncClient(timeout=12) as client:
            resp = await client.get(
                _S2_SEARCH,
                params={
                    "query": title[:100],
                    "fields": "title,abstract,year,externalIds,authors,venue,openAccessPdf",
                    "limit": 3,
                },
                headers={"User-Agent": "ARIA/5.0"},
            )
            if resp.status_code != 200:
                return None
            items = resp.json().get("data", [])
            for item in items:
                if year and item.get("year") and abs(item["year"] - int(re.sub(r'[a-z]', '', year))) > 2:
                    continue
                return item
    except Exception as exc:
        logger.debug("S2 search error: %s", exc)
    return None


def _apply_semantic_scholar(rec: CorpusRecord, item: dict) -> None:
    ext = item.get("externalIds", {}) or {}
    doi = ext.get("DOI", "")
    if doi and not rec.doi:
        rec.doi = doi
        rec.doi_status = "unverified"
    if not rec.abstract:
        rec.abstract = item.get("abstract", "") or ""
    oa_pdf = item.get("openAccessPdf") or {}
    if oa_pdf.get("url"):
        rec.access_status = "open_access"
        if not rec.url:
            rec.url = oa_pdf["url"]


def _guess_access_status(rec: CorpusRecord) -> str:
    """Heuristic: guess access status from ref_type and URL."""
    if rec.ref_type == "web_report" and rec.url:
        return "open_access"
    if rec.ref_type in ("journal_article",):
        # Without explicit OA signal, assume paywalled
        return "paywalled"
    if rec.ref_type in ("book", "book_chapter"):
        return "paywalled"
    return "unknown"


# ---------------------------------------------------------------------------
# Full text fetch for Level 1 open-access papers
# ---------------------------------------------------------------------------

async def _fetch_open_access_text(
    rec: CorpusRecord,
    output_dir: str,
    semaphore: asyncio.Semaphore,
) -> None:
    """Attempt to fetch full text for an open-access Level 1 record."""
    if rec.access_status != "open_access":
        return
    if not rec.url:
        return

    from aria.utils.robots import allowed_async
    from aria.utils.url import ensure_public_http_request

    if not await allowed_async(rec.url):
        rec.access_status = "unavailable"
        return

    async with semaphore:
        await asyncio.sleep(_DEFAULT_REQUEST_DELAY)
        try:
            async with _httpx.AsyncClient(
                timeout=15,
                follow_redirects=True,
                event_hooks={"request": [ensure_public_http_request]},
                headers={"User-Agent": "Mozilla/5.0 (compatible; ARIA/5.0)"},
            ) as client:
                resp = await client.get(rec.url)
            if resp.status_code != 200:
                rec.access_status = "unavailable"
                return

            raw_html = resp.text
            # Strip tags
            text = re.sub(r'<(?:script|style)[^>]*>.*?</(?:script|style)>', '', raw_html,
                          flags=re.DOTALL | re.IGNORECASE)
            text = re.sub(r'<[^>]+>', ' ', text)
            text = text.replace('&amp;', '&').replace('&nbsp;', ' ').replace('&lt;', '<').replace('&gt;', '>')
            text = re.sub(r'\n{3,}', '\n\n', text)
            text = re.sub(r'[ \t]+', ' ', text).strip()

            if len(text) < 300:
                rec.access_status = "unavailable"
                return

            # Build filename from author + year
            slug = _make_slug(rec)
            path = os.path.join(output_dir, "full-texts", f"{slug}.txt")
            os.makedirs(os.path.dirname(path), exist_ok=True)
            with open(path, "w", encoding="utf-8") as fh:
                fh.write(f"TITLE: {rec.title}\n")
                fh.write(f"AUTHORS: {', '.join(rec.authors)}\n")
                fh.write(f"YEAR: {rec.year}\n")
                fh.write(f"DOI: {rec.doi}\n")
                fh.write(f"URL: {rec.url}\n")
                fh.write("=" * 80 + "\n\n")
                fh.write(text[:50000])

            rec.full_text_available = True
            rec.full_text_path = f"full-texts/{slug}.txt"

        except Exception as exc:
            logger.debug("Full-text fetch error for %s: %s", rec.url, exc)
            rec.access_status = "unavailable"


def _make_slug(rec: CorpusRecord) -> str:
    """Create a filename-safe slug from first author + year."""
    first_author = ""
    if rec.authors:
        first_author = rec.authors[0].split(",")[0].strip().lower()
    first_author = re.sub(r"[^a-z0-9]", "", first_author)[:20]
    year = re.sub(r"[^0-9]", "", rec.year or "")[:4]
    title_word = re.sub(r"[^a-z0-9]", "", (rec.title or "").lower().split()[0] if rec.title else "")[:10]
    return f"{first_author}{year}_{title_word}" or "unknown"


# ---------------------------------------------------------------------------
# Main phase entry point
# ---------------------------------------------------------------------------

async def run_citation_crawl_phase(
    mission_config: Any,
    output_dir: str,
    emit_fn: Optional[Callable] = None,
    log: Optional[logging.Logger] = None,
) -> list[CorpusRecord]:
    """Run the full citation crawl phase.

    Args:
        mission_config: Mission config dict or object with citation_crawl section.
        output_dir:     Base output directory for this run.
        emit_fn:        Optional async callable(stage, message, **kwargs) for SSE.
        log:            Optional logger override.

    Returns:
        List of CorpusRecord objects — Level 0 first, then Level 1.
    """
    _log = log or logger
    cfg = _get_citation_crawl_config(mission_config)

    seed_doi = cfg.get("seed_doi", "").strip()
    seed_url = cfg.get("seed_url", "").strip()
    max_refs = int(cfg.get("max_refs", 100))
    resolve_abstracts = bool(cfg.get("resolve_abstracts", True))
    fetch_oa = bool(cfg.get("fetch_open_access", True))
    output_subdir = cfg.get("output_subdir", "citation-graph")
    # Issue #7 fix — configurable concurrency and rate-limit delay
    semaphore_limit = int(cfg.get("max_concurrent", _DEFAULT_SEMAPHORE_LIMIT))
    request_delay = float(cfg.get("request_delay", _DEFAULT_REQUEST_DELAY))
    # Issue #6 fix — pre-parsed refs from PDF upload path
    seed_raw_refs: list[str] = cfg.get("seed_raw_refs") or []
    seed_title: str = cfg.get("seed_title", "")
    crawl_output_dir = os.path.join(output_dir, output_subdir)
    os.makedirs(crawl_output_dir, exist_ok=True)
    os.makedirs(os.path.join(crawl_output_dir, "full-texts"), exist_ok=True)

    async def _emit(stage: str, msg: str, **kw: Any) -> None:
        _log.info("[citation_crawl] %s: %s", stage, msg)
        if emit_fn:
            try:
                await emit_fn(stage, msg, **kw)
            except Exception:
                pass

    await _emit("citation_crawl", f"Starting citation crawl — seed: {seed_doi or seed_url or seed_title or 'PDF upload'}")

    # ── Step 1: Fetch seed paper (Level 0) ──────────────────────────────────
    # Issue #6 fix — if pre-parsed refs supplied (from PDF upload), skip network fetch
    if seed_raw_refs:
        _log.info("Citation crawl: using %d pre-parsed refs from PDF upload", len(seed_raw_refs))
        parser = ReferenceParser()
        parsed_refs = parser.parse_list(seed_raw_refs)
        level0 = CorpusRecord(
            level=0,
            title=seed_title,
            doi=seed_doi,
            access_status="open_access",
            full_text_available=True,
            doi_status="unverified" if seed_doi else "not_attempted",
        )
        await _emit(
            "citation_crawl",
            f"Seed paper (PDF): '{seed_title[:80]}' — {len(parsed_refs)} references parsed",
            ref_count=len(parsed_refs),
        )
    else:
        await _emit("citation_crawl", "Fetching seed paper (Level 0)…")
        fetcher = SeedFetcher()
        try:
            seed_result: SeedResult = await fetcher.fetch(doi=seed_doi, url=seed_url)
        except Exception as exc:
            _log.error("Citation crawl: seed fetch failed: %s", exc)
            return []

        level0 = seed_result.level0_record

        # Save Level 0 full text
        if seed_result.full_text:
            slug = _make_slug(level0) or "seed"
            ft_path = os.path.join(crawl_output_dir, "full-texts", f"{slug}.txt")
            with open(ft_path, "w", encoding="utf-8") as fh:
                fh.write(seed_result.full_text[:100000])
            level0.full_text_available = True
            level0.full_text_path = f"full-texts/{slug}.txt"
            level0.access_status = "open_access"

        parsed_refs = seed_result.parsed_references

        await _emit(
            "citation_crawl",
            f"Seed paper fetched: '{level0.title[:80]}' — "
            f"{len(seed_result.raw_references)} references found",
            ref_count=len(seed_result.raw_references),
        )

    if not parsed_refs:
        await _emit("citation_crawl", "No references extracted from seed paper — stopping.")
        return [level0]

    # ── Step 2: Resolve Level 1 metadata ────────────────────────────────────
    refs_to_process = parsed_refs[:max_refs]
    await _emit(
        "citation_crawl",
        f"Resolving metadata for {len(refs_to_process)} Level 1 references…",
    )

    level1_records: list[CorpusRecord] = []

    if resolve_abstracts:
        semaphore = asyncio.Semaphore(semaphore_limit)  # Issue #7 — configurable
        # Issue #12 fix — emit progress every 10 papers resolved
        _progress_interval = max(1, len(refs_to_process) // 10)
        completed_count = 0

        async def _resolve_with_progress(ref: RefRecord) -> CorpusRecord:
            nonlocal completed_count
            result = await _resolve_level1_metadata(ref, semaphore, request_delay)
            completed_count += 1
            if completed_count % _progress_interval == 0 or completed_count == len(refs_to_process):
                await _emit(
                    "citation_crawl",
                    f"Resolving references… {completed_count}/{len(refs_to_process)}",
                    progress=completed_count,
                    total=len(refs_to_process),
                )
            return result

        tasks = [_resolve_with_progress(ref) for ref in refs_to_process]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        for r in results:
            if isinstance(r, CorpusRecord):
                level1_records.append(r)
            else:
                _log.debug("Level 1 resolution error: %s", r)
                level1_records.append(CorpusRecord(level=1, parse_notes=[str(r)]))
    else:
        # Build minimal records from parsed refs without API calls
        for ref in refs_to_process:
            level1_records.append(CorpusRecord(
                level=1,
                title=ref.get("title", ""),
                authors=ref.get("authors", []),
                year=ref.get("year", ""),
                journal=ref.get("journal", ""),
                volume=ref.get("volume", ""),
                issue=ref.get("issue", ""),
                pages=ref.get("pages", ""),
                url=ref.get("url", ""),
                doi=ref.get("doi", ""),
                ref_type=ref.get("ref_type", "unknown"),
                raw_ref=ref.get("raw", ""),
                doi_status="not_attempted",
                access_status=_guess_access_status(
                    CorpusRecord(ref_type=ref.get("ref_type", ""), url=ref.get("url", ""))
                ),
            ))

    doi_count = sum(1 for r in level1_records if r.doi)
    abstract_count = sum(1 for r in level1_records if r.abstract)
    await _emit(
        "citation_crawl",
        f"Metadata resolved — {doi_count} DOIs, {abstract_count} abstracts",
        doi_count=doi_count,
        abstract_count=abstract_count,
    )

    # ── Step 3: Fetch open-access full texts ─────────────────────────────────
    if fetch_oa:
        oa_candidates = [r for r in level1_records if r.access_status == "open_access" and r.url]
        if oa_candidates:
            await _emit(
                "citation_crawl",
                f"Fetching full text for {len(oa_candidates)} open-access papers…",
            )
            semaphore = asyncio.Semaphore(semaphore_limit)
            tasks = [
                _fetch_open_access_text(r, crawl_output_dir, semaphore)
                for r in oa_candidates
            ]
            await asyncio.gather(*tasks, return_exceptions=True)

        ft_count = sum(1 for r in level1_records if r.full_text_available)
        await _emit(
            "citation_crawl",
            f"Full text retrieved for {ft_count} Level 1 papers",
            full_text_count=ft_count,
        )

    all_records = [level0] + level1_records
    await _emit(
        "citation_crawl",
        f"Citation crawl complete — {len(all_records)} total records "
        f"({1} Level 0, {len(level1_records)} Level 1)",
        total=len(all_records),
    )

    return all_records
