"""PDF collector - searches for PDFs and extracts text."""

from __future__ import annotations

import asyncio
import io
import logging
import os
import tempfile
from datetime import datetime, timezone
from typing import AsyncGenerator, Any, Optional
from urllib.parse import urlparse

import httpx

from .base import BaseCollector

logger = logging.getLogger("aria")

_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (compatible; ARIA Research Collector/1.0; "
        "+https://github.com/aria-platform)"
    ),
    "Accept": "application/pdf,*/*",
}


class PDFCollector(BaseCollector):
    """Discovers PDFs via web search and extracts text with pdfminer."""

    def __init__(
        self,
        max_results: int = 8,
        max_pdf_size_mb: float = 100.0,
        timeout: int = 30,
    ) -> None:
        self._max_results = max_results
        self._max_bytes = int(max_pdf_size_mb * 1024 * 1024)
        self._timeout = timeout

    async def validate(self) -> bool:
        try:
            from pdfminer.high_level import extract_text  # noqa: F401
            return True
        except ImportError:
            logger.warning("PDFCollector: pdfminer.six not installed")
            return False

    async def collect(self, queries: list[str]) -> AsyncGenerator[dict[str, Any], None]:
        """Search for PDFs matching each query and yield extracted text.

        Args:
            queries: Search queries to use for PDF discovery.

        Yields:
            Document dicts with source_type='pdf'.
        """
        seen_urls: set[str] = set()

        for query in queries:
            pdf_query = f"{query} filetype:pdf"
            try:
                urls = await self._find_pdf_urls(pdf_query)
                for url in urls:
                    if url in seen_urls:
                        continue
                    seen_urls.add(url)
                    doc = await self._process_pdf(url, query)
                    if doc:
                        yield doc
                    await asyncio.sleep(0.5)
            except Exception as exc:
                logger.warning("PDFCollector: error for query '%s': %s", query, exc)

    async def _find_pdf_urls(self, query: str) -> list[str]:
        """Search DuckDuckGo for PDF URLs."""
        try:
            from duckduckgo_search import DDGS

            loop = asyncio.get_event_loop()
            results = await loop.run_in_executor(
                None,
                lambda: list(DDGS().text(query, max_results=self._max_results)),
            )
            urls = []
            for r in results:
                href = r.get("href", "")
                if href and (href.lower().endswith(".pdf") or "pdf" in href.lower()):
                    urls.append(href)
                elif href:
                    # Include non-PDF URLs that might redirect to PDF
                    urls.append(href)
            return urls[:self._max_results]
        except Exception as exc:
            logger.debug("PDFCollector: DDGS search failed: %s", exc)
            return []

    async def _process_pdf(self, url: str, query: str) -> Optional[dict[str, Any]]:
        """Download and extract text from a PDF URL.

        Args:
            url: PDF URL.
            query: Original search query.

        Returns:
            Document dict or None on failure.
        """
        text = await self.extract_pdf_text(url)
        if not text or len(text.strip()) < 100:
            return None

        domain = urlparse(url).netloc
        title = _infer_title_from_text(text) or url.split("/")[-1]

        return {
            "url": url,
            "title": title,
            "text": text,
            "source_type": "pdf",
            "platform": domain,
            "language": "en",
            "word_count": len(text.split()),
            "collected_at": datetime.now(timezone.utc).isoformat(),
            "metadata": {"query": query, "domain": domain},
        }

    async def extract_pdf_text(self, url: str) -> Optional[str]:
        """Download a PDF and extract its text content.

        Args:
            url: URL of the PDF file.

        Returns:
            Extracted text, or None on failure.
        """
        try:
            from pdfminer.high_level import extract_text as pdf_extract

            async with httpx.AsyncClient(
                headers=_HEADERS,
                timeout=self._timeout,
                follow_redirects=True,
            ) as client:
                # Stream download to check size
                async with client.stream("GET", url) as resp:
                    if resp.status_code != 200:
                        return None
                    content_type = resp.headers.get("content-type", "")
                    if "pdf" not in content_type and not url.lower().endswith(".pdf"):
                        # Check first bytes to see if it's a PDF
                        first_chunk = b""
                        async for chunk in resp.aiter_bytes(chunk_size=8):
                            first_chunk = chunk
                            break
                        if not first_chunk.startswith(b"%PDF"):
                            return None

                    chunks = []
                    total = 0
                    async for chunk in resp.aiter_bytes(chunk_size=65536):
                        total += len(chunk)
                        if total > self._max_bytes:
                            logger.debug("PDFCollector: PDF too large at %s", url)
                            break
                        chunks.append(chunk)

                pdf_bytes = b"".join(chunks)

            if not pdf_bytes or not pdf_bytes.startswith(b"%PDF"):
                return None

            # Extract text in thread pool to avoid blocking
            loop = asyncio.get_event_loop()
            try:
                text = await loop.run_in_executor(
                    None,
                    lambda: pdf_extract(io.BytesIO(pdf_bytes)),
                )
            except Exception as exc:
                logger.debug("PDFCollector: pdfminer failed for %s: %s — falling back to markitdown", url, exc)
                text = ""
            cleaned = _clean_pdf_text(text)
            # Fallback: if pdfminer produced thin or empty text, try MarkItDown.
            if len(cleaned) < 200:
                try:
                    from aria.engine.utils.markitdown_adapter import convert_bytes
                    md_text = await loop.run_in_executor(
                        None,
                        lambda: convert_bytes(pdf_bytes, url.rsplit("/", 1)[-1] or "file.pdf"),
                    )
                    if len(md_text) > len(cleaned):
                        logger.debug("PDFCollector: markitdown fallback gave %d chars (pdfminer: %d) for %s",
                                     len(md_text), len(cleaned), url)
                        return md_text
                except Exception as exc:
                    logger.debug("PDFCollector: markitdown fallback failed for %s: %s", url, exc)
            return cleaned

        except Exception as exc:
            logger.debug("PDFCollector: extraction failed for %s: %s", url, exc)
            return None


def _clean_pdf_text(text: str) -> str:
    """Clean extracted PDF text."""
    import re
    if not text:
        return ""
    # Remove form feeds and excessive newlines
    text = text.replace("\x0c", "\n")
    text = re.sub(r"\n{3,}", "\n\n", text)
    text = re.sub(r"[ \t]+", " ", text)
    return text.strip()


def _infer_title_from_text(text: str) -> Optional[str]:
    """Try to infer a document title from the first lines of text."""
    lines = [l.strip() for l in text.split("\n") if l.strip()]
    for line in lines[:5]:
        if 10 < len(line) < 200:
            return line
    return None
