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

        result = _parse_extraction(response)

        # Fallback: simpler prompt if JSON parsing failed entirely
        if result is None:
            simple_prompt = _SIMPLE_EXTRACT_PROMPT.format(
                title=doc.get("title", "")[:100],
                text=text[:800],
            )
            response2 = await _call_llm(simple_prompt, _EXTRACT_SYSTEM, max_tokens=400)
            if response2:
                result = _parse_simple_extraction(response2)

        if result is None:
            return None

        result["_source_url"]   = doc.get("url", "")
        result["_source_title"] = doc.get("title", "")
        result["_platform"]     = doc.get("platform", "")
        return result

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
                result = _parse_extraction(response)
                if result:
                    contradictions = result.get("contradictions", [])
                    if contradictions:
                        for c in contradictions:
                            c["subject"] = subject
                        self._contradictions.extend(contradictions)
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


# ── Simple prompt — more reliable on smaller/local models ────────────────────
_SIMPLE_EXTRACT_PROMPT = """Read this text and list what you find.

Title: {title}
Text: {text}

Reply in this exact format (one item per line, comma-separated on each line):
PEOPLE: name1, name2
ORGS: org1, org2
TECH: tech1, tech2
CONCEPTS: concept1, concept2
CLAIM: One important factual claim from the text.
CLAIM: Another factual claim.
"""


def _clean_llm_output(text: str) -> str:
    """Strip thinking tags, markdown fences, and leading/trailing noise."""
    # Remove <think>...</think> blocks (Qwen, DeepSeek)
    text = re.sub(r"<think>.*?</think>", "", text, flags=re.DOTALL | re.IGNORECASE)
    # Remove markdown code fences ```json ... ``` or ``` ... ```
    text = re.sub(r"```(?:json)?\s*", "", text)
    text = re.sub(r"```", "", text)
    return text.strip()


def _repair_json(text: str) -> str:
    """Fix common JSON errors produced by local models."""
    # Trailing commas before } or ]
    text = re.sub(r",\s*([}\]])", r"\1", text)
    # Unquoted True/False/None → JSON booleans/null
    text = re.sub(r"\bTrue\b",  "true",  text)
    text = re.sub(r"\bFalse\b", "false", text)
    text = re.sub(r"\bNone\b",  "null",  text)
    return text


def _parse_extraction(response: str) -> Optional[dict[str, Any]]:
    """Parse LLM response into extraction dict — handles Ollama output quirks."""
    cleaned = _clean_llm_output(response)

    # Try 1: direct parse
    try:
        result = json.loads(cleaned)
        if isinstance(result, dict) and "entities" in result:
            return result
    except (json.JSONDecodeError, ValueError):
        pass

    # Try 2: find first {...} block and parse it
    match = re.search(r"\{.*\}", cleaned, re.DOTALL)
    if match:
        fragment = match.group(0)

        # Try 2a: as-is
        try:
            result = json.loads(fragment)
            if isinstance(result, dict):
                return result
        except (json.JSONDecodeError, ValueError):
            pass

        # Try 2b: after repair
        try:
            result = json.loads(_repair_json(fragment))
            if isinstance(result, dict):
                return result
        except (json.JSONDecodeError, ValueError):
            pass

        # Try 2c: truncated JSON — try to close open brackets
        try:
            frag = fragment
            opens = frag.count("{") - frag.count("}")
            arr_opens = frag.count("[") - frag.count("]")
            if opens > 0 or arr_opens > 0:
                frag += "]" * max(0, arr_opens) + "}" * max(0, opens)
                result = json.loads(_repair_json(frag))
                if isinstance(result, dict):
                    return result
        except (json.JSONDecodeError, ValueError):
            pass

    return None


def _parse_simple_extraction(response: str) -> Optional[dict[str, Any]]:
    """Parse the simple line-format fallback response into an extraction dict."""
    cleaned = _clean_llm_output(response)
    entities: dict[str, list[str]] = {
        "people": [], "organizations": [], "technologies": [],
        "concepts": [], "locations": [],
    }
    claims: list[dict[str, Any]] = []

    label_map = {
        "people":    "people",
        "person":    "people",
        "orgs":      "organizations",
        "org":       "organizations",
        "organizations": "organizations",
        "tech":      "technologies",
        "technology": "technologies",
        "technologies": "technologies",
        "concepts":  "concepts",
        "concept":   "concepts",
        "locations": "locations",
        "location":  "locations",
        "places":    "locations",
    }

    for line in cleaned.splitlines():
        line = line.strip()
        if not line:
            continue
        if ":" not in line:
            continue
        label, _, value = line.partition(":")
        label = label.strip().lower()
        value = value.strip()

        if label == "claim":
            if value:
                claims.append({"claim": value, "confidence": "medium", "subject": ""})
        elif label in label_map:
            etype = label_map[label]
            items = [v.strip() for v in value.split(",") if v.strip()]
            entities[etype].extend(items)

    # Only return if we got something
    if any(entities.values()) or claims:
        return {
            "entities":           entities,
            "claims":             claims,
            "relationships":      [],
            "sentiment_on_topic": "neutral",
            "key_findings":       [c["claim"] for c in claims[:3]],
        }
    return None


async def _call_llm(prompt: str, system: str, max_tokens: int = 800) -> Optional[str]:
    """Call best available LLM — same provider as the cleaner."""
    from aria.engine.cleaner.llm_cleaner import _call_anthropic, _call_openai_compat
    from aria.engine.ensemble.providers import resolve_cleaning_llm
    try:
        provider, model_id, base_url, api_key = resolve_cleaning_llm(None)
        if provider == "anthropic":
            return await _call_anthropic(
                prompt, model_id, api_key, system,
                max_tokens=max_tokens, temperature=0.1,
            )
        else:
            return await _call_openai_compat(
                prompt, model_id, api_key, base_url,
                system, max_tokens=max_tokens, temperature=0.1,
            )
    except Exception as exc:
        logger.debug("KG LLM call failed: %s", exc)
    return None
