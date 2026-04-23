"""ClinicalTrials.gov collector — registered clinical studies worldwide."""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone
from typing import AsyncGenerator, Any
from urllib.parse import quote

import httpx

from .base import BaseCollector

logger = logging.getLogger("aria")

_CT_API = "https://clinicaltrials.gov/api/v2/studies"


class ClinicalTrialsCollector(BaseCollector):
    """Collects clinical trial data from ClinicalTrials.gov (official US NIH registry).

    No API key required. Returns real-time data from 450K+ registered studies.
    """

    def __init__(
        self,
        max_results: int = 20,
        country_codes: list[str] | None = None,
        status_filter: str = "RECRUITING,COMPLETED",
    ) -> None:
        self._max_results = max_results
        self._country_codes = country_codes or []
        self._status_filter = status_filter

    async def collect(self, queries: list[str]) -> AsyncGenerator[dict[str, Any], None]:
        seen_ids: set[str] = set()
        count = 0

        for query in queries[:4]:
            if count >= self._max_results:
                break
            async for doc in self._search_trials(query, seen_ids):
                if count >= self._max_results:
                    break
                yield doc
                count += 1
            await asyncio.sleep(0.4)

    async def _search_trials(
        self, query: str, seen_ids: set[str]
    ) -> AsyncGenerator[dict[str, Any], None]:
        try:
            params: dict[str, Any] = {
                "query.term": query,
                "pageSize": min(10, self._max_results),
                "fields": "NCTId,BriefTitle,BriefSummary,Condition,InterventionName,Phase,OverallStatus,StartDate,PrimaryCompletionDate,LeadSponsorName,LocationCountry,StudyType,EnrollmentCount",
                "format": "json",
            }
            if self._status_filter:
                params["filter.overallStatus"] = self._status_filter
            if self._country_codes:
                params["query.locn"] = " OR ".join(self._country_codes[:5])

            async with httpx.AsyncClient(timeout=20) as client:
                resp = await client.get(_CT_API, params=params)
                if resp.status_code != 200:
                    logger.debug("ClinicalTrials: HTTP %s for '%s'", resp.status_code, query)
                    return

                data = resp.json()
                studies = data.get("studies", [])

                for study in studies:
                    proto = study.get("protocolSection", {})
                    id_module = proto.get("identificationModule", {})
                    desc_module = proto.get("descriptionModule", {})
                    cond_module = proto.get("conditionsModule", {})
                    arm_module = proto.get("armsInterventionsModule", {})
                    design_module = proto.get("designModule", {})
                    status_module = proto.get("statusModule", {})
                    sponsor_module = proto.get("sponsorCollaboratorsModule", {})
                    contacts_module = proto.get("contactsLocationsModule", {})

                    nct_id = id_module.get("nctId", "")
                    if nct_id in seen_ids:
                        continue
                    seen_ids.add(nct_id)

                    title = id_module.get("briefTitle", "") or id_module.get("officialTitle", "")
                    if not title:
                        continue

                    summary = desc_module.get("briefSummary", "") or ""
                    conditions = ", ".join(cond_module.get("conditions", [])[:5])
                    interventions_raw = arm_module.get("interventions", [])[:3]
                    interventions = ", ".join(
                        i.get("name", "") for i in interventions_raw if i.get("name")
                    )
                    phase = ", ".join(design_module.get("phases", []))
                    status = status_module.get("overallStatus", "")
                    start_date = status_module.get("startDateStruct", {}).get("date", "")
                    enrollment = design_module.get("enrollmentInfo", {}).get("count", "")
                    sponsor = sponsor_module.get("leadSponsor", {}).get("name", "")

                    locations = contacts_module.get("locations", [])[:3]
                    countries = list({loc.get("country", "") for loc in locations if loc.get("country")})

                    text_parts = [title]
                    if conditions:
                        text_parts.append(f"Conditions: {conditions}")
                    if interventions:
                        text_parts.append(f"Interventions: {interventions}")
                    if phase:
                        text_parts.append(f"Phase: {phase}")
                    text_parts.append(f"Status: {status}")
                    if sponsor:
                        text_parts.append(f"Sponsor: {sponsor}")
                    if start_date:
                        text_parts.append(f"Start Date: {start_date}")
                    if enrollment:
                        text_parts.append(f"Enrollment: {enrollment}")
                    if countries:
                        text_parts.append(f"Countries: {', '.join(countries)}")
                    if summary:
                        text_parts.append(f"\n{summary[:800]}")

                    text = "\n".join(text_parts).strip()
                    if len(text) < 40:
                        continue

                    yield {
                        "url": f"https://clinicaltrials.gov/study/{nct_id}",
                        "title": title,
                        "text": text,
                        "source_type": "clinical",
                        "platform": "clinical_trials",
                        "language": "en",
                        "word_count": len(text.split()),
                        "collected_at": datetime.now(timezone.utc).isoformat(),
                        "metadata": {
                            "source": "clinicaltrials_gov",
                            "nct_id": nct_id,
                            "status": status,
                            "phase": phase,
                            "conditions": conditions,
                            "sponsor": sponsor,
                            "countries": countries,
                            "query": query,
                        },
                    }

        except Exception as exc:
            logger.warning("ClinicalTrialsCollector: error for '%s': %s", query, exc)
