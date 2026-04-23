"""HTML report generator for research collection runs."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional


def generate_report(
    documents: list[dict],
    topic: str,
    output_dir: Path,
    stats: Optional[dict] = None,
    knowledge_graph: Optional[dict] = None,
    gap_analysis: Optional[dict] = None,
    images: Optional[list[dict]] = None,
    methodology: Optional[dict] = None,
) -> str:
    """Generate an HTML report summarising the collection results.

    Args:
        documents: List of (cleaned) document dicts.
        topic: Research topic string.
        output_dir: Directory to write the report into.
        stats: Optional stats dict (collected, cleaned, sources, etc.)
        knowledge_graph: Optional KG dict from KnowledgeGraph.to_dict()
        gap_analysis: Optional gap dict from detect_gaps()
        images: Optional list of image dicts from extract_images_from_docs()

    Returns:
        Path to the generated HTML report file as a string.
    """
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    report_path = output_dir / "report.html"

    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    stats = stats or {}

    total = len(documents)
    relevant = sum(1 for d in documents if d.get("is_relevant", True))
    avg_relevance = (
        sum(float(d.get("relevance_score", 0.5) or 0.5) for d in documents) / total
        if total else 0.0
    )

    source_counts: dict[str, int] = {}
    for doc in documents:
        platform = doc.get("platform") or doc.get("source_type") or "unknown"
        source_counts[platform] = source_counts.get(platform, 0) + 1

    content_types: dict[str, int] = {}
    for doc in documents:
        ct = doc.get("content_type", "unknown") or "unknown"
        content_types[ct] = content_types.get(ct, 0) + 1

    html = _build_html(
        topic=topic,
        now=now,
        total=total,
        relevant=relevant,
        avg_relevance=avg_relevance,
        source_counts=source_counts,
        content_types=content_types,
        documents=documents,
        stats=stats,
        knowledge_graph=knowledge_graph or {},
        gap_analysis=gap_analysis or {},
        images=images or [],
        methodology=methodology or {},
    )

    report_path.write_text(html, encoding="utf-8")
    return str(report_path)


def _build_html(
    topic: str,
    now: str,
    total: int,
    relevant: int,
    avg_relevance: float,
    source_counts: dict[str, int],
    content_types: dict[str, int],
    documents: list[dict],
    stats: dict,
    knowledge_graph: dict,
    gap_analysis: dict,
    images: list[dict],
    methodology: dict,
) -> str:
    methodology_section = _build_methodology_section(methodology)
    source_rows = "\n".join(
        f"<tr><td>{platform}</td><td>{count}</td></tr>"
        for platform, count in sorted(source_counts.items(), key=lambda x: -x[1])
    )
    content_rows = "\n".join(
        f"<tr><td>{ct}</td><td>{count}</td></tr>"
        for ct, count in sorted(content_types.items(), key=lambda x: -x[1])
    )
    doc_cards = "\n".join(_doc_card(i + 1, doc) for i, doc in enumerate(documents[:200]))

    # Knowledge graph sections
    kg_section = _build_kg_section(knowledge_graph)
    gap_section = _build_gap_section(gap_analysis)
    image_section = _build_image_section(images, topic)

    # Extra stats from intelligence
    contradictions = len(knowledge_graph.get("contradictions", []))
    gaps = len(gap_analysis.get("gaps", []))
    entities = knowledge_graph.get("total_entities", 0)
    n_images = len(images)

    # Extra stat cards (only if non-zero)
    extra_stats = ""
    if entities:
        extra_stats += f"""<div class="stat-card">
    <div class="value">{entities}</div>
    <div class="label">Entities Found</div>
  </div>"""
    if contradictions:
        extra_stats += f"""<div class="stat-card warn">
    <div class="value">{contradictions}</div>
    <div class="label">Contradictions</div>
  </div>"""
    if gaps:
        extra_stats += f"""<div class="stat-card">
    <div class="value">{gaps}</div>
    <div class="label">Research Gaps</div>
  </div>"""
    if n_images:
        extra_stats += f"""<div class="stat-card">
    <div class="value">{n_images}</div>
    <div class="label">Images Found</div>
  </div>"""

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>ARIA Research Report: {_esc(topic)}</title>
<style>
  * {{ box-sizing: border-box; margin: 0; padding: 0; }}
  body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
         background: #f5f7fa; color: #1a1a2e; line-height: 1.6; }}
  .header {{ background: linear-gradient(135deg, #1a1a2e 0%, #16213e 50%, #0f3460 100%);
             color: white; padding: 40px 20px; text-align: center; }}
  .header h1 {{ font-size: 2em; margin-bottom: 10px; }}
  .header .meta {{ opacity: 0.75; font-size: 0.9em; }}
  .container {{ max-width: 1200px; margin: 0 auto; padding: 20px; }}
  .stats-grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(160px, 1fr));
                 gap: 15px; margin: 20px 0; }}
  .stat-card {{ background: white; border-radius: 8px; padding: 20px; text-align: center;
                box-shadow: 0 2px 8px rgba(0,0,0,0.08); }}
  .stat-card.warn {{ border-top: 3px solid #f59e0b; }}
  .stat-card .value {{ font-size: 2em; font-weight: bold; color: #0f3460; }}
  .stat-card.warn .value {{ color: #b45309; }}
  .stat-card .label {{ color: #666; font-size: 0.85em; margin-top: 4px; }}
  .section {{ background: white; border-radius: 8px; padding: 20px; margin: 20px 0;
              box-shadow: 0 2px 8px rgba(0,0,0,0.08); }}
  .section h2 {{ font-size: 1.2em; margin-bottom: 15px; color: #0f3460;
                 border-bottom: 2px solid #e8ecf4; padding-bottom: 8px; }}
  table {{ width: 100%; border-collapse: collapse; }}
  th, td {{ padding: 8px 12px; text-align: left; border-bottom: 1px solid #e8ecf4; }}
  th {{ background: #f5f7fa; font-weight: 600; color: #444; }}
  /* Entity grid */
  .entity-grid {{ display: flex; flex-wrap: wrap; gap: 8px; margin-top: 10px; }}
  .entity-chip {{ display: inline-flex; align-items: center; gap: 6px;
                  background: #e8f4fd; color: #0369a1; border-radius: 20px;
                  padding: 4px 12px; font-size: 0.82em; font-weight: 500; }}
  .entity-chip .count {{ background: #0369a1; color: white; border-radius: 10px;
                         padding: 1px 6px; font-size: 0.8em; }}
  /* Contradiction cards */
  .contradiction {{ background: #fff7ed; border: 1px solid #fed7aa;
                    border-radius: 6px; padding: 12px 16px; margin: 8px 0; }}
  .contradiction .severity {{ font-size: 0.75em; font-weight: 700; text-transform: uppercase;
                               color: #c2410c; margin-bottom: 4px; }}
  .contradiction .claims {{ font-size: 0.88em; color: #444; margin: 6px 0; }}
  .contradiction .claims strong {{ color: #92400e; }}
  .contradiction .explanation {{ font-size: 0.85em; color: #78350f; font-style: italic; }}
  /* Gap cards */
  .gap-card {{ background: #f0f9ff; border: 1px solid #bae6fd;
               border-radius: 6px; padding: 12px 16px; margin: 8px 0; }}
  .gap-card .question {{ font-weight: 600; color: #0c4a6e; margin-bottom: 4px; }}
  .gap-card .reason {{ font-size: 0.85em; color: #0369a1; }}
  .gap-card .follow-ups {{ margin-top: 8px; }}
  .gap-card .follow-ups span {{ display: inline-block; background: #e0f2fe;
                                 color: #0369a1; border-radius: 4px; padding: 2px 8px;
                                 font-size: 0.78em; margin: 2px; }}
  /* Image gallery */
  .image-gallery {{ display: grid; grid-template-columns: repeat(auto-fill, minmax(200px, 1fr));
                    gap: 12px; margin-top: 12px; }}
  .image-card {{ background: white; border: 1px solid #e8ecf4; border-radius: 8px;
                 overflow: hidden; }}
  .image-card img {{ width: 100%; height: 140px; object-fit: cover; display: block; }}
  .image-card .img-caption {{ padding: 8px 10px; font-size: 0.8em; color: #555; }}
  .image-card .img-source {{ padding: 0 10px 8px; font-size: 0.75em; color: #888;
                              white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }}
  /* Perspectives list */
  .perspective-list {{ list-style: none; }}
  .perspective-list li {{ padding: 6px 0; border-bottom: 1px solid #f0f0f0;
                           font-size: 0.9em; color: #555; }}
  .perspective-list li::before {{ content: "→ "; color: #0f3460; font-weight: bold; }}
  /* Doc cards */
  .doc-card {{ background: white; border-radius: 8px; padding: 16px 20px; margin: 12px 0;
               box-shadow: 0 1px 4px rgba(0,0,0,0.06); border-left: 4px solid #0f3460; }}
  .doc-card.low-relevance {{ border-left-color: #ccc; }}
  .doc-card h3 {{ font-size: 1em; margin-bottom: 6px; }}
  .doc-card h3 a {{ color: #0f3460; text-decoration: none; }}
  .doc-card h3 a:hover {{ text-decoration: underline; }}
  .doc-meta {{ font-size: 0.8em; color: #666; margin-bottom: 8px; }}
  .doc-meta span {{ margin-right: 12px; }}
  .badge {{ display: inline-block; padding: 2px 8px; border-radius: 12px;
            font-size: 0.75em; font-weight: 600; }}
  .badge-platform {{ background: #e8f4fd; color: #0369a1; }}
  .badge-type {{ background: #f0fdf4; color: #166534; }}
  .badge-relevance-high {{ background: #dcfce7; color: #166534; }}
  .badge-relevance-mid {{ background: #fef9c3; color: #854d0e; }}
  .badge-relevance-low {{ background: #fef2f2; color: #991b1b; }}
  .summary {{ font-size: 0.9em; color: #444; }}
  .footer {{ text-align: center; color: #999; font-size: 0.8em; padding: 30px 20px; }}
  .alert {{ background: #fff7ed; border-left: 4px solid #f59e0b;
            padding: 12px 16px; border-radius: 4px; margin: 12px 0;
            font-size: 0.9em; color: #92400e; }}
  /* Methodology section */
  .method-grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(280px, 1fr));
                  gap: 16px; margin-top: 12px; }}
  .method-block {{ background: #f8fafc; border: 1px solid #e2e8f0;
                   border-radius: 8px; padding: 14px 16px; }}
  .method-block h4 {{ font-size: 0.85em; text-transform: uppercase; letter-spacing: 0.05em;
                      color: #64748b; margin-bottom: 10px; font-weight: 700; }}
  .method-item {{ display: flex; justify-content: space-between; align-items: flex-start;
                  padding: 5px 0; border-bottom: 1px solid #e8ecf4; font-size: 0.88em; }}
  .method-item:last-child {{ border-bottom: none; }}
  .method-item .mkey {{ color: #475569; flex-shrink: 0; margin-right: 12px; }}
  .method-item .mval {{ color: #1e293b; font-weight: 500; text-align: right; word-break: break-word; }}
  .method-tag {{ display: inline-block; background: #dbeafe; color: #1d4ed8;
                 border-radius: 4px; padding: 1px 7px; font-size: 0.78em;
                 margin: 2px 2px 2px 0; font-weight: 500; }}
  .method-tag.green {{ background: #dcfce7; color: #166534; }}
  .method-tag.purple {{ background: #f3e8ff; color: #7c3aed; }}
  .method-tag.orange {{ background: #ffedd5; color: #c2410c; }}
  .query-list {{ list-style: none; margin-top: 6px; }}
  .query-list li {{ font-size: 0.84em; color: #334155; padding: 3px 0;
                    border-bottom: 1px solid #f1f5f9; }}
  .query-list li::before {{ content: "›  "; color: #94a3b8; }}
  .citation-badge {{ display: inline-flex; align-items: center; gap: 6px;
                     background: #faf5ff; border: 1px solid #e9d5ff;
                     color: #7c3aed; border-radius: 6px; padding: 4px 10px;
                     font-size: 0.85em; margin-top: 6px; }}
</style>
</head>
<body>
<div class="header">
  <h1>ARIA Research Report</h1>
  <h2 style="font-size:1.2em;font-weight:normal;margin-top:8px;">{_esc(topic)}</h2>
  <p class="meta">Generated {now}</p>
</div>

<div class="container">

<div class="stats-grid">
  <div class="stat-card">
    <div class="value">{total}</div>
    <div class="label">Documents Collected</div>
  </div>
  <div class="stat-card">
    <div class="value">{relevant}</div>
    <div class="label">Relevant Documents</div>
  </div>
  <div class="stat-card">
    <div class="value">{avg_relevance:.2f}</div>
    <div class="label">Avg Relevance Score</div>
  </div>
  <div class="stat-card">
    <div class="value">{len(source_counts)}</div>
    <div class="label">Platforms</div>
  </div>
  {extra_stats}
</div>

{methodology_section}
{kg_section}
{gap_section}
{image_section}

<div class="section">
  <h2>Source Breakdown</h2>
  <table>
    <thead><tr><th>Platform</th><th>Documents</th></tr></thead>
    <tbody>{source_rows}</tbody>
  </table>
</div>

<div class="section">
  <h2>Content Types</h2>
  <table>
    <thead><tr><th>Content Type</th><th>Documents</th></tr></thead>
    <tbody>{content_rows}</tbody>
  </table>
</div>

<div class="section">
  <h2>Documents ({min(total, 200)} shown)</h2>
  {doc_cards}
</div>

</div>
<div class="footer">
  Generated by ARIA Research Platform &middot; {now}
</div>
</body>
</html>"""


def _build_methodology_section(m: dict) -> str:
    if not m:
        return ""

    # ── Collection method block ──────────────────────────────────────────
    method = m.get("collection_method", "standard")
    method_label = "Domain Plan (ARIA 5.0)" if method == "domain_plan" else "Standard Pipeline"

    domains = m.get("domains", [])
    domain_tags = "".join(
        f'<span class="method-tag">{_esc(d)}</span>' for d in domains
    ) or '<span style="color:#94a3b8;font-size:0.85em;">All sources</span>'

    countries = m.get("countries", [])
    country_tags = "".join(
        f'<span class="method-tag green">{_esc(c)}</span>' for c in countries
    ) or '<span style="color:#94a3b8;font-size:0.85em;">Global</span>'

    sources = m.get("sources_used", [])
    source_tags = "".join(
        f'<span class="method-tag purple">{_esc(s)}</span>' for s in sources[:20]
    )

    # ── LLM block ────────────────────────────────────────────────────────
    llm_provider = m.get("llm_provider", "unknown")
    llm_model = m.get("llm_model", "unknown")
    cleaning = m.get("cleaning_method", "llm")

    # ── Query block ───────────────────────────────────────────────────────
    queries = m.get("queries", [])
    query_items = "\n".join(
        f"<li>{_esc(q)}</li>" for q in queries[:30]
    )
    query_count = m.get("query_count", len(queries))

    # ── Citation block ────────────────────────────────────────────────────
    citation_depth = m.get("citation_depth", 0)
    citation_docs = m.get("citation_docs_fetched", 0)
    citation_html = ""
    if citation_depth > 0:
        citation_html = f"""
<div class="citation-badge">
  🔗 Citation Intelligence active — depth {citation_depth} — {citation_docs} cited papers fetched
</div>"""

    # ── Timing block ─────────────────────────────────────────────────────
    duration = m.get("duration_seconds")
    duration_str = f"{duration:.0f}s" if duration else "—"
    dedup = m.get("dedup_method", "URL + content fingerprint")
    started = m.get("started_at", "")[:19].replace("T", " ") if m.get("started_at") else "—"

    return f"""<div class="section">
  <h2>🔬 Collection Methodology</h2>
  <p style="font-size:0.9em;color:#64748b;margin-bottom:16px;">
    How ARIA collected and processed the information in this report.
  </p>

  <div class="method-grid">

    <div class="method-block">
      <h4>Collection Strategy</h4>
      <div class="method-item">
        <span class="mkey">Method</span>
        <span class="mval">{_esc(method_label)}</span>
      </div>
      <div class="method-item">
        <span class="mkey">Domains targeted</span>
        <span class="mval">{domain_tags}</span>
      </div>
      <div class="method-item">
        <span class="mkey">Countries / regions</span>
        <span class="mval">{country_tags}</span>
      </div>
      <div class="method-item">
        <span class="mkey">Active sources</span>
        <span class="mval">{len(sources)}</span>
      </div>
      <div style="margin-top:8px;">{source_tags}</div>
      {citation_html}
    </div>

    <div class="method-block">
      <h4>Processing Pipeline</h4>
      <div class="method-item">
        <span class="mkey">LLM provider</span>
        <span class="mval">{_esc(llm_provider)}</span>
      </div>
      <div class="method-item">
        <span class="mkey">LLM model</span>
        <span class="mval">{_esc(llm_model)}</span>
      </div>
      <div class="method-item">
        <span class="mkey">Cleaning method</span>
        <span class="mval">{_esc(cleaning)}</span>
      </div>
      <div class="method-item">
        <span class="mkey">Deduplication</span>
        <span class="mval">{_esc(dedup)}</span>
      </div>
      <div class="method-item">
        <span class="mkey">Relevance scoring</span>
        <span class="mval">Multi-dimensional (0.0 – 1.0)</span>
      </div>
      <div class="method-item">
        <span class="mkey">Duration</span>
        <span class="mval">{_esc(duration_str)}</span>
      </div>
      <div class="method-item">
        <span class="mkey">Started at</span>
        <span class="mval">{_esc(started)} UTC</span>
      </div>
    </div>

    <div class="method-block">
      <h4>Search Queries Used ({query_count} total)</h4>
      <ul class="query-list">
        {query_items}
        {"<li style='color:#94a3b8;font-style:italic;'>… and more</li>" if query_count > 30 else ""}
      </ul>
    </div>

  </div>
</div>"""


def _build_kg_section(kg: dict) -> str:
    if not kg or not kg.get("top_entities"):
        return ""

    top_entities = kg.get("top_entities", [])[:30]
    contradictions = kg.get("contradictions", [])

    entity_chips = "\n".join(
        f'<span class="entity-chip">{_esc(e["name"])} '
        f'<span class="count">{e["mention_count"]}</span></span>'
        for e in top_entities
    )

    contradiction_html = ""
    if contradictions:
        contra_cards = "\n".join(
            f"""<div class="contradiction">
  <div class="severity">⚠ {_esc(c.get('severity', 'unknown'))} contradiction — {_esc(c.get('subject', ''))}</div>
  <div class="claims">
    <strong>Source A:</strong> {_esc(c.get('source_a', ''))}<br>
    <em>{_esc(c.get('claim_a', ''))}</em>
  </div>
  <div class="claims">
    <strong>Source B:</strong> {_esc(c.get('source_b', ''))}<br>
    <em>{_esc(c.get('claim_b', ''))}</em>
  </div>
  <div class="explanation">{_esc(c.get('explanation', ''))}</div>
</div>"""
            for c in contradictions[:10]
        )
        contradiction_html = f"""
<h3 style="margin:16px 0 8px;font-size:1em;color:#b45309;">
  ⚠ {len(contradictions)} Contradiction(s) Detected
</h3>
{contra_cards}"""

    return f"""<div class="section">
  <h2>🧠 Knowledge Graph — {_esc(str(kg.get('total_entities', 0)))} entities, {_esc(str(kg.get('total_claims', 0)))} claims</h2>
  <div class="entity-grid">
    {entity_chips}
  </div>
  {contradiction_html}
</div>"""


def _build_gap_section(ga: dict) -> str:
    if not ga or not ga.get("has_gaps"):
        return ""

    gaps = ga.get("gaps", [])
    perspectives = ga.get("missing_perspectives", [])

    gap_cards = "\n".join(
        f"""<div class="gap-card">
  <div class="question">{_esc(g.get('question', ''))}</div>
  <div class="reason">{_esc(g.get('reason', ''))}</div>
  <div class="follow-ups">
    {''.join(f'<span>{_esc(q)}</span>' for q in g.get('follow_up_queries', [])[:3])}
  </div>
</div>"""
        for g in gaps[:8]
    )

    perspectives_html = ""
    if perspectives:
        items = "\n".join(f"<li>{_esc(p)}</li>" for p in perspectives[:6])
        perspectives_html = f"""
<h3 style="margin:16px 0 8px;font-size:1em;color:#0c4a6e;">Missing Perspectives</h3>
<ul class="perspective-list">{items}</ul>"""

    return f"""<div class="section">
  <h2>🔍 Research Gap Analysis — {len(gaps)} gap(s) identified</h2>
  {gap_cards}
  {perspectives_html}
</div>"""


def _build_image_section(images: list[dict], topic: str) -> str:
    if not images:
        return ""

    img_cards = "\n".join(
        f"""<div class="image-card">
  <img src="{_esc(img['url'])}" alt="{_esc(img.get('alt_text', topic))}"
       loading="lazy" onerror="this.parentElement.style.display='none'">
  <div class="img-caption">{_esc(img.get('caption') or img.get('alt_text', ''))}</div>
  <div class="img-source">{_esc(img.get('source_title', img.get('source_url', '')))}</div>
</div>"""
        for img in images[:24]
    )

    return f"""<div class="section">
  <h2>🖼 Images — {len(images)} found</h2>
  <div class="image-gallery">
    {img_cards}
  </div>
</div>"""


def _doc_card(idx: int, doc: dict) -> str:
    title = _esc(doc.get("title") or f"Document {idx}")
    url = doc.get("url", "")
    platform = _esc(doc.get("platform") or "")
    content_type = _esc(doc.get("content_type") or "")
    relevance = doc.get("relevance_score")
    summary = _esc(doc.get("summary") or "")
    word_count = doc.get("word_count", "")

    rel_str = ""
    card_class = "doc-card"
    if relevance is not None:
        r = float(relevance)
        if r >= 0.7:
            rel_cls = "badge-relevance-high"
        elif r >= 0.4:
            rel_cls = "badge-relevance-mid"
        else:
            rel_cls = "badge-relevance-low"
            card_class = "doc-card low-relevance"
        rel_str = f'<span class="badge {rel_cls}">Relevance: {r:.2f}</span>'

    title_html = (
        f'<a href="{_esc(url)}" target="_blank">{title}</a>' if url else title
    )
    platform_badge = f'<span class="badge badge-platform">{platform}</span>' if platform else ""
    type_badge = f'<span class="badge badge-type">{content_type}</span>' if content_type else ""
    wc_span = f'<span>{word_count} words</span>' if word_count else ""
    summary_html = f'<p class="summary">{summary}</p>' if summary else ""

    return f"""<div class="{card_class}">
  <h3>{title_html}</h3>
  <div class="doc-meta">
    {platform_badge} {type_badge} {rel_str} {wc_span}
  </div>
  {summary_html}
</div>"""


def _esc(text: Any) -> str:
    s = str(text) if text is not None else ""
    return (
        s.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
        .replace("'", "&#39;")
    )
