# Mission Files

Mission YAML is the primary configuration surface for ARIA runs. Each mission defines what to collect, how deep to go, how to clean it, and how to export it.

## Structure

```yaml
mission:
  name: "My Research Mission"

collection:
  topic: "AI safety benchmarks 2025"
  intent: "What evaluation frameworks exist, who builds them, what gaps remain"
  depth_level: 3              # 1–5
  max_documents: 2000
  max_per_source: 200
  languages:
    collect: [en]
    translate_to: en

  sources:
    enabled:
      - web
      - pdf
      - academic
      - reddit
      - youtube
      # auth sources (silently skipped if no credentials)
      - twitter
      - zotero
    priority:
      academic: 10            # higher = more quota allocated

  user_urls:                  # explicit URLs to always scrape
    - https://example.com/report.pdf

  zotero_config:              # only needed when zotero is enabled
    mode: local               # local | cloud
    collection_key: ""        # empty = all items
    library_type: user        # user | group
    library_id: ""            # required for cloud mode
    api_key: ""               # required for cloud mode; or set ZOTERO_API_KEY
    max_items: 500

  rss_feeds:                  # only used when rss source is enabled
    - https://feeds.example.com/research.atom

authenticated_sources:
  enabled: true
  platforms:
    - ieee
    - springer

llm_sources:
  enabled: false              # set true to query LLMs as research sources
  models:
    - provider: openai
      model_id: gpt-4o-mini
      enabled: true
    - provider: anthropic
      model_id: claude-3-5-haiku-latest
      enabled: true
    - provider: ollama
      model_id: llama3.1:8b
      enabled: false
  query_settings:
    parallel: true
    delay_between_queries: 2
    skip_duplicate_queries: true
  comparison:
    enabled: true
    min_models_for_comparison: 2

cleaning:
  # research_goal drives the Smart Cleaning Agent automatically.
  # Leave blank — it is populated from collection.intent at runtime.
  research_goal: ""

  # instructions is an optional global override.
  # Leave blank to use automatic smart mode.
  instructions: ""

  # Per-source overrides — leave blank for smart automatic mode.
  per_source:
    academic: ""
    reddit: ""
    zotero: ""

  chunking:
    enabled: false
    chunk_size: 8000
    overlap: 500

  output_schema:
    is_relevant: bool
    relevance_score: float
    title: string
    summary: string
    key_topics:
      - string
    entities:
      organizations:
        - string
      locations:
        - string
      people:
        - string
    quality_issues:
      - string

output:
  formats: [json, csv, markdown]
  sort_by: relevance_score    # relevance_score | collected_at | word_count
  sort_order: desc            # asc | desc
```

## Depth levels

| Level | Name | Approx. documents | Deep crawl |
|---|---|---|---|
| 1 | Surface | ~50 | None |
| 2 | Standard | ~200 | None |
| 3 | Deep | ~500 | 1 BFS level |
| 4 | Thorough | ~1,500 | 2 BFS levels |
| 5 | Maximum | 5,000+ | Full recursive |

## Valid sources

### Free
`web` `pdf` `academic` `youtube` `reddit` `hackernews` `wikipedia` `stackoverflow` `medium` `devto` `substack` `rss` `user_urls`

### Auth required
`twitter` `linkedin` `notion` `slack` `podcast` `vimeo` `zotero`

Auth sources are silently skipped if their credentials are not configured. The run continues with the remaining sources.

## Smart cleaning

The `output_schema` is the only required field. Leave `instructions` and `research_goal` blank — the Smart Cleaning Agent detects the content type of each document automatically and applies the correct extraction strategy.

Set `research_goal` explicitly only if you want a custom goal string different from the collection topic/intent.

## Zotero import

When `zotero` is in the enabled sources list, ARIA imports items from your Zotero library before running other agents. The scraped content joins the same deduplication and cleaning pipeline.

For **local mode**, Zotero desktop must be running when you start the ARIA run.

For **cloud mode**, get your API key from [zotero.org/settings/keys](https://www.zotero.org/settings/keys) and find your library ID at [zotero.org/settings/keys/new](https://www.zotero.org/settings/keys/new).

## Examples

Templates live in `missions/examples/`:

| File | Purpose |
|---|---|
| `default.yaml` | General-purpose web + academic run |
| `academic_research.yaml` | Deep academic literature review |
| `county_ai_policies.yaml` | Government policy collection with explicit URLs |
