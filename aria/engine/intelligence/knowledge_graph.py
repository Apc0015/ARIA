"""
Knowledge Graph — extracts entities, relationships, and claims from documents.
Detects contradictions between sources.
Builds a networkx graph for export and analysis.
"""

from __future__ import annotations

import json
import logging
import os
import re
from collections import defaultdict
from typing import Any, Optional

logger = logging.getLogger("aria")

try:
    import networkx as nx
    _NX_AVAILABLE = True
except ImportError:
    _NX_AVAILABLE = False
    logger.debug("networkx not installed — knowledge graph export disabled")


_EXTRACT_SYSTEM = (
    "You are a knowledge extraction engine. "
    "Extract structured facts, entities, and claims from research text."
)

_EXTRACT_PROMPT = """Extract structured knowledge from this document.

Title: {title}
Source: {platform} — {source_type}
Text (truncated): {text}

Return ONLY valid JSON:
{{
  "entities": {{
    "people": ["name1", "name2"],
    "organizations": ["org1", "org2"],
    "technologies": ["tech1", "tech2"],
    "concepts": ["concept1", "concept2"],
    "locations": ["loc1", "loc2"]
  }},
  "claims": [
    {{
      "claim": "A specific factual claim made in this document",
      "confidence": "high|medium|low",
      "subject": "entity this claim is about"
    }}
  ],
  "relationships": [
    {{
      "from": "entity A",
      "relation": "verb/relationship type",
      "to": "entity B"
    }}
  ],
  "sentiment_on_topic": "positive|negative|neutral|mixed",
  "key_findings": ["finding 1", "finding 2"]
}}
"""

_CONTRADICTION_PROMPT = """You are a fact-checker. Review these claims about the same subject from different sources.

Subject: {subject}

Claims:
{claims_text}

Identify any contradictions — where sources make conflicting factual claims.

Return ONLY valid JSON:
{{
  "contradictions": [
    {{
      "claim_a": "First claim",
      "source_a": "Source of claim A",
      "claim_b": "Conflicting claim",
      "source_b": "Source of claim B",
      "severity": "major|minor",
      "explanation": "Why these contradict"
    }}
  ],
  "consensus": "What most sources agree on",
  "uncertainty": "What remains disputed or unclear"
}}
"""


class KnowledgeGraph:
    """
    Builds and queries a knowledge graph from collected documents.

    Nodes: entities (people, orgs, technologies, concepts)
    Edges: relationships + co-occurrence
    Contradictions: conflicting claims detected by LLM
    """

    def __init__(self) -> None:
        self._graph = nx.DiGraph() if _NX_AVAILABLE else None
        self._entities: dict[str, dict[str, Any]] = {}
        self._claims: list[dict[str, Any]] = []
        self._contradictions: list[dict[str, Any]] = []
        self._doc_extractions: list[dict[str, Any]] = []

    async def build_from_documents(
        self,
        docs: list[dict[str, Any]],
        topic: str,
        max_docs_to_extract: int = 80,
    ) -> None:
        """
        Extract entities/claims/relationships from top documents.
        Uses LLM for extraction — skips if no LLM available.
        """
        if not docs:
            return

        # Only process top relevant docs
        relevant = sorted(
            docs,
            key=lambda d: d.get("relevance_score", 0) or 0,
            reverse=True,
        )[:max_docs_to_extract]

        logger.info("Knowledge graph: extracting from %d documents", len(relevant))

        for doc in relevant:
            extraction = await self._extract_from_doc(doc)
            if extraction:
                self._doc_extractions.append(extraction)
                self._merge_entities(extraction, doc)
                if self._graph is not None:
                    self._add_to_graph(extraction, doc)

        # Find contradictions
        await self._detect_contradictions()

        logger.info(
            "Knowledge graph built: %d entities, %d claims, %d contradictions",
            len(self._entities),
            len(self._claims),
            len(self._contradictions),
        )

    async def _extract_from_doc(self, doc: dict[str, Any]) -> Optional[dict[str, Any]]:
        """LLM extraction of entities/claims from one document."""
        text = (doc.get("text") or doc.get("summary") or "")[:2000]
        if len(text) < 100:
            return None

        prompt = _EXTRACT_PROMPT.format(
            title=doc.get("title", "")[:200],
            platform=doc.get("platform", ""),
            source_type=doc.get("source_type", ""),
            text=text,
        )

        response = await _call_llm(prompt, _EXTRACT_SYSTEM, max_tokens=800)
        if not response:
            return None

        match = re.search(r"\{.*\}", response, re.DOTALL)
        if not match:
            return None
        try:
            result = json.loads(match.group(0))
            result["_source_url"] = doc.get("url", "")
            result["_source_title"] = doc.get("title", "")
            result["_platform"] = doc.get("platform", "")
            return result
        except (json.JSONDecodeError, ValueError):
            return None

    def _merge_entities(self, extraction: dict[str, Any], doc: dict[str, Any]) -> None:
        """Merge extracted entities into global entity store."""
        entities = extraction.get("entities", {})
        url = doc.get("url", "")

        for etype, names in entities.items():
            for name in (names or []):
                name = name.strip()
                if not name:
                    continue
                key = name.lower()
                if key not in self._entities:
                    self._entities[key] = {
                        "name": name,
                        "type": etype,
                        "mention_count": 0,
                        "sources": [],
                    }
                self._entities[key]["mention_count"] += 1
                if url not in self._entities[key]["sources"]:
                    self._entities[key]["sources"].append(url)

        # Merge claims
        for claim in (extraction.get("claims") or []):
            claim["_source_url"] = url
            claim["_source_title"] = doc.get("title", "")
            self._claims.append(claim)

    def _add_to_graph(self, extraction: dict[str, Any], doc: dict[str, Any]) -> None:
        """Add nodes and edges to networkx graph."""
        if self._graph is None:
            return

        url = doc.get("url", "")
        entities = extraction.get("entities", {})

        # Add entity nodes
        all_names = []
        for etype, names in entities.items():
            for name in (names or []):
                name = name.strip()
                if not name:
                    continue
                if not self._graph.has_node(name):
                    self._graph.add_node(name, entity_type=etype, mention_count=0, sources=[])
                self._graph.nodes[name]["mention_count"] += 1
                if url not in self._graph.nodes[name]["sources"]:
                    self._graph.nodes[name]["sources"].append(url)
                all_names.append(name)

        # Add explicit relationships
        for rel in (extraction.get("relationships") or []):
            frm = (rel.get("from") or "").strip()
            to = (rel.get("to") or "").strip()
            relation = (rel.get("relation") or "related_to").strip()
            if frm and to:
                self._graph.add_edge(frm, to, relation=relation, source=url)

        # Add co-occurrence edges (entities in same doc)
        for i, a in enumerate(all_names):
            for b in all_names[i+1:]:
                if not self._graph.has_edge(a, b):
                    self._graph.add_edge(a, b, relation="co-occurs", weight=0, source=url)
                self._graph[a][b]["weight"] = self._graph[a][b].get("weight", 0) + 1

    async def _detect_contradictions(self) -> None:
        """Group claims by subject and find contradictions."""
        if not self._claims:
            return

        # Group claims by subject
        by_subject: dict[str, list[dict]] = defaultdict(list)
        for claim in self._claims:
            subject = (claim.get("subject") or "").strip().lower()
            if subject:
                by_subject[subject].append(claim)

        # Check subjects with 3+ claims from different sources (most likely to have contradictions)
        checked = 0
        for subject, claims in sorted(by_subject.items(), key=lambda x: -len(x[1])):
            if len(claims) < 3 or checked >= 5:
                break

            # Only check if claims come from different sources
            sources = {c.get("_source_url", "") for c in claims}
            if len(sources) < 2:
                continue

            claims_text = "\n".join(
                f"[{c.get('_source_title', c.get('_source_url', 'unknown'))[:60]}]: {c.get('claim', '')}"
                for c in claims[:8]
            )

            prompt = _CONTRADICTION_PROMPT.format(
                subject=subject,
                claims_text=claims_text,
            )

            response = await _call_llm(prompt, "You are a fact-checker. Respond with JSON only.", max_tokens=600)
            if response:
                match = re.search(r"\{.*\}", response, re.DOTALL)
                if match:
                    try:
                        result = json.loads(match.group(0))
                        contradictions = result.get("contradictions", [])
                        if contradictions:
                            for c in contradictions:
                                c["subject"] = subject
                            self._contradictions.extend(contradictions)
                    except (json.JSONDecodeError, ValueError):
                        pass
            checked += 1

    # ─── Export ──────────────────────────────────────────────────────────────

    def to_dict(self) -> dict[str, Any]:
        """Export full knowledge graph as serialisable dict."""
        top_entities = sorted(
            self._entities.values(),
            key=lambda e: e["mention_count"],
            reverse=True,
        )[:50]

        graph_data = None
        if self._graph is not None and len(self._graph.nodes) > 0:
            try:
                from networkx.readwrite import json_graph
                graph_data = json_graph.node_link_data(self._graph)
            except Exception:
                pass

        return {
            "top_entities": top_entities,
            "total_entities": len(self._entities),
            "total_claims": len(self._claims),
            "contradictions": self._contradictions,
            "has_contradictions": bool(self._contradictions),
            "graph": graph_data,
        }

    def get_contradictions(self) -> list[dict[str, Any]]:
        return self._contradictions

    def get_top_entities(self, n: int = 20) -> list[dict[str, Any]]:
        return sorted(
            self._entities.values(),
            key=lambda e: e["mention_count"],
            reverse=True,
        )[:n]

    def summary(self) -> str:
        """Human-readable summary of the knowledge graph."""
        lines = [
            f"Knowledge Graph Summary",
            f"  Entities: {len(self._entities)}",
            f"  Claims: {len(self._claims)}",
            f"  Contradictions: {len(self._contradictions)}",
        ]
        if self._contradictions:
            lines.append("\nContradictions found:")
            for c in self._contradictions[:3]:
                lines.append(f"  [{c.get('severity','?')}] {c.get('subject','?')}: {c.get('explanation','')[:100]}")
        top = self.get_top_entities(5)
        if top:
            lines.append("\nTop entities:")
            for e in top:
                lines.append(f"  {e['name']} ({e['type']}) — mentioned {e['mention_count']}x")
        return "\n".join(lines)


async def _call_llm(prompt: str, system: str, max_tokens: int = 800) -> Optional[str]:
    ant_key = os.getenv("ANTHROPIC_API_KEY")
    or_key = os.getenv("OPENROUTER_API_KEY")
    oai_key = os.getenv("OPENAI_API_KEY")
    try:
        if ant_key:
            from aria.engine.cleaner.llm_cleaner import _call_anthropic
            return await _call_anthropic(
                prompt, "claude-3-haiku-20240307", ant_key, system,
                max_tokens=max_tokens, temperature=0.1,
            )
        elif or_key:
            from aria.engine.cleaner.llm_cleaner import _call_openai_compat
            return await _call_openai_compat(
                prompt, "openai/gpt-4o-mini", or_key, "https://openrouter.ai/api/v1",
                system, max_tokens=max_tokens, temperature=0.1,
            )
        elif oai_key:
            from aria.engine.cleaner.llm_cleaner import _call_openai_compat
            return await _call_openai_compat(
                prompt, "gpt-4o-mini", oai_key, "https://api.openai.com/v1",
                system, max_tokens=max_tokens, temperature=0.1,
            )
    except Exception as exc:
        logger.debug("KG LLM call failed: %s", exc)
    return None
