"""
Multi-dimensional relevance scorer.

Scores each document on 5 axes without requiring any external API:
  1. Semantic keyword overlap   (fast, always works)
  2. Source authority           (domain reputation heuristic)
  3. Recency                    (newer = more relevant for fast-moving topics)
  4. Information density        (content richness)
  5. Embedding similarity       (optional — requires sentence-transformers)

Final score: weighted combination → 0.0–1.0
"""

from __future__ import annotations

import logging
import math
import re
from datetime import datetime, timezone
from typing import Any, Optional
from urllib.parse import urlparse

logger = logging.getLogger("aria")

# ─── Source authority table ───────────────────────────────────────────────────
# Score 0.0–1.0 for known domains. Unknown → 0.5 baseline.

_AUTHORITY: dict[str, float] = {
    # Academic / Scientific
    "arxiv.org": 0.95, "pubmed.ncbi.nlm.nih.gov": 0.95, "scholar.google.com": 0.90,
    "nature.com": 0.95, "science.org": 0.95, "cell.com": 0.93,
    "ieeexplore.ieee.org": 0.90, "acm.org": 0.90, "dl.acm.org": 0.90,
    "springer.com": 0.88, "sciencedirect.com": 0.88, "jstor.org": 0.85,
    "semanticscholar.org": 0.87, "ncbi.nlm.nih.gov": 0.92,
    "biorxiv.org": 0.80, "medrxiv.org": 0.80, "ssrn.com": 0.78,
    # News
    "reuters.com": 0.88, "apnews.com": 0.88, "bbc.com": 0.85, "bbc.co.uk": 0.85,
    "nytimes.com": 0.83, "theguardian.com": 0.82, "wsj.com": 0.83,
    "ft.com": 0.83, "economist.com": 0.85, "bloomberg.com": 0.83,
    "wired.com": 0.78, "arstechnica.com": 0.78, "techcrunch.com": 0.72,
    "technologyreview.com": 0.85, "scientificamerican.com": 0.87,
    # Government / Official
    "gov": 0.88, "edu": 0.85, "who.int": 0.90, "cdc.gov": 0.90,
    "nih.gov": 0.92, "europa.eu": 0.85, "un.org": 0.85,
    # Technical
    "github.com": 0.72, "stackoverflow.com": 0.75, "docs.python.org": 0.85,
    # Low authority
    "medium.com": 0.55, "substack.com": 0.55, "wordpress.com": 0.40,
    "blogspot.com": 0.35, "reddit.com": 0.50,
}


def _domain_authority(url: str) -> float:
    """Return authority score for a URL's domain."""
    if not url:
        return 0.5
    try:
        host = urlparse(url).netloc.lower().lstrip("www.")
    except Exception:
        return 0.5

    # Exact match
    if host in _AUTHORITY:
        return _AUTHORITY[host]

    # TLD match (e.g. .gov, .edu)
    for tld, score in _AUTHORITY.items():
        if host.endswith(f".{tld}") or host == tld:
            return score

    # Partial domain match
    for domain, score in _AUTHORITY.items():
        if "." in domain and domain in host:
            return score

    return 0.5  # unknown → neutral


def _keyword_overlap(text: str, topic: str, intent: str) -> float:
    """
    Token overlap between document text and (topic + intent).
    Returns 0.0–1.0.
    """
    if not text:
        return 0.0

    combined = f"{topic} {intent}".lower()
    query_tokens = set(re.findall(r"\b\w{3,}\b", combined))
    if not query_tokens:
        return 0.5

    text_lower = text.lower()
    text_tokens = set(re.findall(r"\b\w{3,}\b", text_lower))

    if not text_tokens:
        return 0.0

    # Jaccard-style + frequency boost
    overlap = query_tokens & text_tokens
    jaccard = len(overlap) / len(query_tokens | text_tokens)

    # Frequency boost: how often do query terms appear in text
    freq_total = sum(text_lower.count(tok) for tok in overlap)
    freq_boost = min(1.0, freq_total / (10 * max(1, len(query_tokens))))

    return min(1.0, jaccard * 2 + freq_boost * 0.3)


def _recency_score(doc: dict[str, Any]) -> float:
    """
    Score based on when the document was published/collected.
    Very recent (< 6 months) → high. Old (> 5 years) → low.
    """
    # Try to find a date in collected_at, published_date, or text
    date_str = (
        doc.get("published_date") or
        doc.get("collected_at") or
        doc.get("metadata", {}).get("published_date", "") if isinstance(doc.get("metadata"), dict) else ""
    )

    if date_str:
        try:
            from dateutil import parser as dateparser
            pub_date = dateparser.parse(str(date_str))
            if pub_date:
                now = datetime.now(timezone.utc)
                if pub_date.tzinfo is None:
                    pub_date = pub_date.replace(tzinfo=timezone.utc)
                age_days = (now - pub_date).days
                # Score: 1.0 for today, 0.7 for 1 year ago, 0.4 for 3 years, 0.2 for 5+ years
                if age_days < 30:
                    return 1.0
                elif age_days < 180:
                    return 0.9
                elif age_days < 365:
                    return 0.8
                elif age_days < 730:
                    return 0.7
                elif age_days < 1095:
                    return 0.5
                elif age_days < 1825:
                    return 0.35
                else:
                    return 0.2
        except Exception:
            pass

    # No date → neutral
    return 0.6


def _information_density(text: str) -> float:
    """
    Measure how information-rich the text is.
    Penalises very short, very repetitive, or boilerplate content.
    Returns 0.0–1.0.
    """
    if not text:
        return 0.0

    words = text.split()
    total = len(words)
    if total < 20:
        return 0.1
    if total < 50:
        return 0.3

    # Type-token ratio (lexical diversity)
    unique = len(set(w.lower() for w in words))
    ttr = unique / total

    # Sentence structure (avg sentence length — too long or too short = bad)
    sentences = re.split(r"[.!?]+", text)
    sentences = [s.strip() for s in sentences if len(s.strip()) > 10]
    avg_sent_len = total / max(1, len(sentences))
    sent_score = 1.0 - abs(avg_sent_len - 20) / 40  # optimal ~20 words/sentence
    sent_score = max(0.0, min(1.0, sent_score))

    # Length score (more content = better, up to a point)
    len_score = min(1.0, math.log10(max(1, total)) / 4)  # log10(10000) = 4

    return (ttr * 0.4 + sent_score * 0.3 + len_score * 0.3)


# ─── Optional embedding similarity ───────────────────────────────────────────

_encoder = None
_encoder_tried = False


def _get_encoder():
    """Lazy-load sentence-transformers encoder. Returns None if not installed."""
    global _encoder, _encoder_tried
    if _encoder_tried:
        return _encoder
    _encoder_tried = True
    try:
        from sentence_transformers import SentenceTransformer
        _encoder = SentenceTransformer("all-MiniLM-L6-v2")
        logger.info("Semantic scorer: sentence-transformers loaded (all-MiniLM-L6-v2)")
    except ImportError:
        logger.debug("sentence-transformers not installed — semantic embedding disabled")
        _encoder = None
    except Exception as exc:
        logger.debug("sentence-transformers load failed: %s", exc)
        _encoder = None
    return _encoder


_intent_embedding_cache: dict[str, Any] = {}


def _embedding_similarity(text: str, topic: str, intent: str) -> Optional[float]:
    """
    Compute cosine similarity between doc and research intent using embeddings.
    Returns None if sentence-transformers unavailable.
    """
    encoder = _get_encoder()
    if encoder is None:
        return None

    try:
        import numpy as np
        query = f"{topic} {intent}".strip()

        if query not in _intent_embedding_cache:
            _intent_embedding_cache[query] = encoder.encode(query, convert_to_numpy=True)
        q_emb = _intent_embedding_cache[query]

        snippet = text[:1000]
        d_emb = encoder.encode(snippet, convert_to_numpy=True)

        # Cosine similarity
        sim = float(np.dot(q_emb, d_emb) / (np.linalg.norm(q_emb) * np.linalg.norm(d_emb) + 1e-9))
        return max(0.0, min(1.0, sim))
    except Exception as exc:
        logger.debug("Embedding similarity failed: %s", exc)
        return None


# ─── Main scorer ─────────────────────────────────────────────────────────────

_WEIGHTS = {
    "keyword":   0.30,
    "authority": 0.25,
    "density":   0.20,
    "recency":   0.15,
    "embedding": 0.10,  # bonus if available
}

_WEIGHTS_NO_EMBED = {
    "keyword":   0.35,
    "authority": 0.28,
    "density":   0.22,
    "recency":   0.15,
}


def score_document(
    doc: dict[str, Any],
    topic: str,
    intent: str = "",
    use_embeddings: bool = True,
) -> dict[str, float]:
    """
    Compute multi-dimensional relevance score for a document.

    Returns:
        Dict with individual dimension scores + 'total' (0.0–1.0).
    """
    text = doc.get("text", "")
    url = doc.get("url", "")

    keyword   = _keyword_overlap(text, topic, intent)
    authority = _domain_authority(url)
    density   = _information_density(text)
    recency   = _recency_score(doc)

    embed_sim = None
    if use_embeddings:
        embed_sim = _embedding_similarity(text, topic, intent)

    if embed_sim is not None:
        total = (
            keyword   * _WEIGHTS["keyword"] +
            authority * _WEIGHTS["authority"] +
            density   * _WEIGHTS["density"] +
            recency   * _WEIGHTS["recency"] +
            embed_sim * _WEIGHTS["embedding"]
        )
        # Renormalise (weights sum to 1.0 only when embedding present)
        total = min(1.0, total / sum(_WEIGHTS.values()))
    else:
        w = _WEIGHTS_NO_EMBED
        total = (
            keyword   * w["keyword"] +
            authority * w["authority"] +
            density   * w["density"] +
            recency   * w["recency"]
        )

    return {
        "keyword_score":    round(keyword,   3),
        "authority_score":  round(authority, 3),
        "density_score":    round(density,   3),
        "recency_score":    round(recency,   3),
        "embedding_score":  round(embed_sim, 3) if embed_sim is not None else None,
        "total":            round(total, 3),
    }


def score_and_annotate(
    docs: list[dict[str, Any]],
    topic: str,
    intent: str = "",
    use_embeddings: bool = True,
) -> list[dict[str, Any]]:
    """
    Score all documents and inject `relevance_score` + `score_breakdown` fields.
    Replaces or augments the LLM-assigned relevance_score.

    Strategy: take the MAX of LLM score and heuristic score.
    If LLM didn't run, heuristic score stands alone.
    """
    for doc in docs:
        scores = score_document(doc, topic, intent, use_embeddings=use_embeddings)
        heuristic = scores["total"]
        llm_score = doc.get("relevance_score")

        if llm_score is not None:
            try:
                final = max(float(llm_score), heuristic)
            except (ValueError, TypeError):
                final = heuristic
        else:
            final = heuristic

        doc["relevance_score"] = round(final, 3)
        doc["is_relevant"] = final >= 0.45
        doc["score_breakdown"] = scores

    return docs
