# Citation Graph Agent — Deep Literature Exploration

## Overview

The **Citation Graph Agent** extends ARIA's research capability by recursively collecting papers cited in the initial collection results. This enables:

- 🎯 **Discovery of foundational papers** — automatically finds seminal works cited by collected papers
- 📊 **Literature genealogy** — maps citation networks to understand paper relationships
- ⭐ **Influence scoring** — ranks papers by citation count for authority detection
- 🔄 **Recursive expansion** — depth-configurable citation traversal (1-3 levels)
- 🚫 **Deduplication** — avoids fetching the same paper twice

## Architecture

```
Initial Collection (18 agents)
    ↓
    [Web, Academic, Reddit, GitHub, etc.]
    ↓
    200–500 documents
    ↓
Citation Expansion Phase (NEW)
    ↓
    [Extract citations from papers]
    ↓
    [Fetch cited papers from DOI, arXiv, etc.]
    ↓
    [Rate-limited async fetching]
    ↓
    100–500+ additional documents
    ↓
Smart Cleaning Agent
    ↓
Structured output with relevance scores
```

## Usage

### 1. Via Mission YAML

Enable citation expansion in your mission file:

```yaml
collection:
  topic: "transformer attention mechanisms"
  sources: [web, academic, github]
  depth_level: 2
  
citation_expansion:
  enabled: true
  max_depth: 2              # Follow citations up to 2 levels deep
  max_citations_per_paper: 20
  only_academic: true       # Only expand from academic papers
```

### 2. Via CLI

```bash
# Run with citation expansion
python -m aria.cli \
  --topic "blockchain scalability" \
  --citations-enabled \
  --citations-depth 2
```

### 3. Programmatic

```python
from aria.orchestrator.citation_expansion import CitationPipeline, CitationExpansionConfig
import asyncio

async def main():
    # Configure citation expansion
    citation_config = CitationExpansionConfig(
        enabled=True,
        max_depth=2,
        max_citations_per_paper=15,
        max_concurrent_fetches=5,
        only_academic=True,
    )
    
    # Create pipeline
    pipeline = CitationPipeline(citation_config)
    
    # After initial collection, expand
    result = await pipeline.run_expansion_phase(
        initial_documents=collected_docs,
        run_id="research_run_001",
    )
    
    # Merge results
    all_documents = collected_docs + result["new_documents"]
    
    print(f"Initial docs: {result['stats']['initial_count']}")
    print(f"Cited papers: {result['stats']['cited_papers_found']}")
    print(f"Expansion ratio: {result['stats']['expansion_ratio']:.1f}x")

asyncio.run(main())
```

## How It Works

### Citation Extraction

The `CitationExtractor` parses the References/Bibliography section of papers:

```
References

[1] Smith et al. (2020). "Attention is All You Need". ICML.
[2] Vaswani et al. (2017). arXiv:1706.03762
[3] Devlin et al. "BERT: Pre-training of Deep..." DOI: 10.18653/v1/N19-1423
```

Extracts:
- **DOI**: Direct link via Crossref API
- **arXiv ID**: Fetch from arxiv.org
- **Title**: Parse title and search via Semantic Scholar
- **Authors**: Extract author list
- **Year**: Parse publication year
- **URL**: Extract any direct links

### Citation Fetching

Three-tier fetching strategy:

1. **DOI** (fastest) → Crossref API
   ```
   DOI: 10.1145/3132847.3132938
   ↓
   Crossref API → full metadata
   ```

2. **arXiv** → arXiv API
   ```
   arXiv: 2306.12345
   ↓
   arxiv.org/api → title, authors, year
   ```

3. **Title search** → Semantic Scholar
   ```
   Title: "Attention is All You Need"
   ↓
   Semantic Scholar search → metadata + URL
   ```

### Rate Limiting

- Max 5 concurrent fetches (configurable)
- 100ms delay between batches
- Graceful timeout (10s per request)
- Deduplication (no duplicate DOI/URL fetches)

### Influence Scoring

Papers ranked by citation count:

```
Citation Count → Influence Score
0–1            → 0.2
2–5            → 0.3–0.5
10–50          → 0.6–0.8
100+           → 0.9
```

Score is logarithmic: `influence = min(0.9, (count^0.4) / 10)`

## Configuration Options

### CitationExpansionConfig

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `enabled` | bool | True | Enable/disable citation expansion |
| `max_depth` | int | 2 | Recursion depth (1-3 recommended) |
| `max_citations_per_paper` | int | 20 | Max citations extracted per paper |
| `max_concurrent_fetches` | int | 5 | Concurrent API calls |
| `only_academic` | bool | True | Only expand from academic papers |

### Performance Tuning

**Fast mode** (5-10 min):
```yaml
citation_expansion:
  max_depth: 1              # Single level only
  max_citations_per_paper: 10
  max_concurrent_fetches: 10
```

**Thorough mode** (15-30 min):
```yaml
citation_expansion:
  max_depth: 2              # Two levels
  max_citations_per_paper: 25
  max_concurrent_fetches: 5
```

**Exhaustive mode** (30-60 min):
```yaml
citation_expansion:
  max_depth: 3              # Full traversal
  max_citations_per_paper: 50
  max_concurrent_fetches: 3  # Slow to respect API limits
```

## Output Example

```json
{
  "new_documents": [
    {
      "title": "Attention Is All You Need",
      "authors": ["Vaswani", "Shazeer", "Parmar", ...],
      "year": 2017,
      "doi": "10.5555/3295222.3295349",
      "url": "https://arxiv.org/abs/1706.03762",
      "source_type": "academic_paper",
      "platform": "citations_depth_1",
      "citation_source": true,
      "influence_score": 0.92
    },
    ...
  ],
  "stats": {
    "initial_count": 245,
    "academic_count": 189,
    "cited_papers_found": 387,
    "expansion_ratio": 2.05
  }
}
```

## Integration Points

### With Smart Cleaning Agent

All expanded documents flow through the cleaning pipeline:

```python
# After citation expansion
expanded_docs = await citation_pipeline.run_expansion_phase(initial_docs)
all_docs = initial_docs + expanded_docs["new_documents"]

# Then pass to cleaner
cleaned = await cleaner.clean_batch(all_docs, research_goal)
```

### With Export System

Expanded documents tagged with:
- `citation_source: true` — came from citation expansion
- `influence_score: 0.0–1.0` — citation influence
- `platform: citations_depth_N` — recursion level

Enables filtering/sorting in exports:

```python
# In report generation
highly_cited = [d for d in docs if d.get("influence_score", 0) > 0.7]
foundational = sorted(docs, key=lambda d: d.get("year", 9999))
```

## API Sources

### Free (No auth required)

- **Crossref API** — DOI metadata
- **arXiv API** — Paper fetching
- **Semantic Scholar** — Title-based search
- **Unpaywall** — Open access detection

### Optional (Subscription-based)

- **IEEE Xplore** — `IEEE_API_KEY`
- **Elsevier** — `ELSEVIER_API_KEY`
- **JSTOR** — institutional access

## Limitations & Future

### Current Limitations

- PDF/HTML extraction limited to text references (no visual citations)
- arXiv-heavy (academic bias toward CS/physics)
- No paywalled paper fetching (Sci-Hub not integrated)
- Rate limiting prevents mass crawling

### Future Enhancements

- [ ] Visual citation detection (from PDFs)
- [ ] Citation context extraction ("why was X cited?")
- [ ] Author co-citation networks
- [ ] Citation sentiment analysis
- [ ] Integration with institutional library systems
- [ ] PageRank-based influence (not just count)

## Troubleshooting

### "No citations found"

- Ensure `only_academic: false` if using non-academic sources
- Check that source documents have readable References sections
- Increase `max_citations_per_paper` threshold

### "API rate limiting"

- Reduce `max_concurrent_fetches`
- Increase delay between batches
- Check Crossref/Semantic Scholar API status

### "Duplicate documents"

- Should not happen (dedup built-in)
- If occurs, check for URL normalization issues

### "Missing papers"

- DOI registry is incomplete; some papers not indexed
- arXiv only covers preprints; published versions may differ
- Institutional access required for paywalled content

## Examples

### Example 1: Literature Review

```python
# Start with broad search
result = await aria.run({
    "topic": "machine learning interpretability",
    "sources": ["academic", "arxiv"],
    "citation_expansion": {"max_depth": 2}
})

# Result: ~200 papers → ~400 citations → 600 total
# Sorted by relevance + influence
```

### Example 2: Competitive Intelligence

```python
# Track who's citing competitors
result = await aria.run({
    "topic": "GPT-4 applications in enterprise",
    "sources": ["web", "arxiv", "github"],
    "citation_expansion": {"enabled": true}
})

# Expand to find academic citations
# Identify which papers are most cited in industry
```

### Example 3: Student Research

```python
# Thesis background research
result = await aria.run({
    "topic": "transformer architecture variants",
    "sources": ["academic"],
    "citation_expansion": {
        "max_depth": 3,
        "max_citations_per_paper": 30
    }
})

# Comprehensive genealogy of transformer papers
# Identify foundational vs. recent work
```

---

**Questions?** See [README.md](README.md) or open an issue on GitHub.
