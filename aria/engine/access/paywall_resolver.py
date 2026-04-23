"""Paywall resolution for academic content via open access routes."""

from __future__ import annotations

import asyncio
import logging
import os
from typing import Optional
from urllib.parse import quote

import httpx

logger = logging.getLogger("aria")


class PaywallResolver:
    """Attempts to find open-access versions of paywalled content.

    Tries, in order:
    1. Unpaywall API (DOI-based)
    2. Semantic Scholar open access PDFs
    3. PubMed Central (PMC)
    4. arXiv (for papers that may have a preprint)

    Set UNPAYWALL_EMAIL env var to your email address as required by
    Unpaywall's Terms of Service: https://unpaywall.org/terms
    """

    UNPAYWALL_BASE = "https://api.unpaywall.org/v2"
    _UNPAYWALL_EMAIL_DEFAULT = "research@aria-platform.org"

    def __init__(self, timeout: int = 15) -> None:
        self._timeout = timeout
        # Read at instantiation time so env var changes take effect without reimport
        self._unpaywall_email = os.getenv(
            "UNPAYWALL_EMAIL", self._UNPAYWALL_EMAIL_DEFAULT
        )

    @property
    def UNPAYWALL_EMAIL(self) -> str:  # noqa: N802 — preserve existing attribute name
        return self._unpaywall_email

    async def resolve(self, url: str, doi: Optional[str] = None) -> Optional[str]:
        """Try to find a free, full-text version of the given resource.

        Args:
            url: Original URL (may be paywalled).
            doi: Digital Object Identifier if known.

        Returns:
            A URL pointing to free full text, or None if not found.
        """
        if doi:
            result = await self._try_unpaywall(doi)
            if result:
                return result

            result = await self._try_semantic_scholar(doi)
            if result:
                return result

            result = await self._try_pmc(doi)
            if result:
                return result

        return None

    async def _try_unpaywall(self, doi: str) -> Optional[str]:
        try:
            encoded_doi = quote(doi, safe="")
            endpoint = f"{self.UNPAYWALL_BASE}/{encoded_doi}?email={self.UNPAYWALL_EMAIL}"
            async with httpx.AsyncClient(timeout=self._timeout) as client:
                resp = await client.get(endpoint)
                if resp.status_code == 200:
                    data = resp.json()
                    # Check for best OA location
                    best_loc = data.get("best_oa_location")
                    if best_loc:
                        pdf_url = best_loc.get("url_for_pdf") or best_loc.get("url")
                        if pdf_url:
                            logger.debug("Unpaywall resolved DOI %s -> %s", doi, pdf_url)
                            return pdf_url
        except Exception as exc:
            logger.debug("Unpaywall lookup failed for DOI %s: %s", doi, exc)
        return None

    async def _try_semantic_scholar(self, doi: str) -> Optional[str]:
        try:
            endpoint = f"https://api.semanticscholar.org/graph/v1/paper/DOI:{quote(doi, safe='')}?fields=openAccessPdf"
            async with httpx.AsyncClient(timeout=self._timeout) as client:
                resp = await client.get(endpoint)
                if resp.status_code == 200:
                    data = resp.json()
                    oa = data.get("openAccessPdf")
                    if oa and oa.get("url"):
                        logger.debug("Semantic Scholar resolved DOI %s -> %s", doi, oa["url"])
                        return oa["url"]
        except Exception as exc:
            logger.debug("Semantic Scholar lookup failed for DOI %s: %s", doi, exc)
        return None

    async def _try_pmc(self, doi: str) -> Optional[str]:
        try:
            # Use PubMed ID converter to find PMC ID
            endpoint = (
                f"https://www.ncbi.nlm.nih.gov/pmc/utils/idconv/v1.0/?ids={quote(doi, safe='')}&format=json"
            )
            async with httpx.AsyncClient(timeout=self._timeout) as client:
                resp = await client.get(endpoint)
                if resp.status_code == 200:
                    data = resp.json()
                    records = data.get("records", [])
                    if records:
                        pmcid = records[0].get("pmcid")
                        if pmcid:
                            pmc_url = f"https://www.ncbi.nlm.nih.gov/pmc/articles/{pmcid}/pdf/"
                            logger.debug("PMC resolved DOI %s -> %s", doi, pmc_url)
                            return pmc_url
        except Exception as exc:
            logger.debug("PMC lookup failed for DOI %s: %s", doi, exc)
        return None
