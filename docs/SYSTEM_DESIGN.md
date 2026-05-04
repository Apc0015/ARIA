# ARIA System Design

## Executive Overview

**ARIA** (Agentic Research Intelligence Architecture) is a fully automated research collection and intelligence platform that deploys 18+ parallel web agents, processes results through smart LLM-powered cleaning, and exports structured research findings in 6 formats. The system is designed for speed, scalability, and flexibility across multiple LLM providers and data sources.

**Version:** 5.0.0  
**Core Language:** Python 3.11+  
**Architecture Pattern:** Distributed Agent-based Pipeline with Microservice API

---

## 1. Architecture Layers

### 1.1 High-Level Data Flow

```
User Input (CLI/API)
    ↓
Mission Config (YAML)
    ↓
[Query Expansion] → Semantic expansion into 5-8 queries
    ↓
[Parallel Collection Layer] → 18 agents run simultaneously
    ├─ Web Agents (Search, Reddit, HN, Wiki, etc.)
    ├─ Academic Agents (arXiv, PubMed, Semantic Scholar)
    ├─ Media Agents (YouTube, Podcasts, Vimeo)
    ├─ Social Agents (Twitter, LinkedIn, Slack)
    └─ Knowledge Agents (Zotero, Notion, User URLs)
    ↓
[Deduplication] → URL hash + content fingerprint
    ↓
[Smart Cleaning Agent] → LLM auto-detects content type + extracts
    ↓
[Storage] → Raw + cleaned documents stored
    ↓
[Export] → JSON, CSV, Markdown, HTML, ZIP
    ↓
Output to User (Download/API)
```

---

## 2. Core Modules

### 2.1 **Orchestrator (`aria/orchestrator/`)**

The master orchestration engine controlling the entire pipeline.

**Key Components:**
- **`master.py`** – Main orchestrator; coordinates all phases
- **`aggregator.py`** – Collects results from all sources; merges, deduplicates
- **`quality.py`** – Quality assurance checks; relevance scoring
- **`strategy.py`** – Strategy selection based on depth level (1–5)

**Responsibilities:**
- Execute collection plan from mission config
- Dispatch parallel tasks via `asyncio.gather()`
- Monitor collection status
- Trigger deduplication and cleaning phases
- Manage memory across phases

### 2.2 **Sources (`aria/sources/`)**

18+ parallel collection agents, each implementing the `BaseCollector` interface.

**Collector Categories:**

| Category | Agents | Auth Required | Fallback |
|----------|--------|---|---|
| **Web** | SerpAPI, DuckDuckGo, Google, Bing | Optional | DuckDuckGo |
| **Academic** | arXiv, PubMed, Semantic Scholar, IEEE, Elsevier | Optional | Free tier |
| **Media** | YouTube (yt-dlp), Podcasts (RSS + Whisper), Vimeo | Optional | RSS feed |
| **Social** | Twitter/X, LinkedIn, Slack, Reddit, Medium, dev.to | Optional | Public APIs |
| **Knowledge** | Zotero, Notion, User URLs | Optional | Local store |
| **News** | BBC, Reuters, AP, NPR, Guardian (RSS) | Optional | Generic news |
| **Multilingual** | DuckDuckGo across 12 language regions | None | Built-in |
| **Government** | data.gov, regulations.gov | Optional | DuckDuckGo |
| **GitHub** | DuckDuckGo site:github.com OR PyGithub API | Optional | DuckDuckGo |

**Source Groups:**

Sources are classified into two groups that control their visibility in the UI:

| Group | Description | UI Default |
|-------|-------------|------------|
| `standard` | Web, academic, social, media — general research sources | Visible, opt-in per source |
| `advanced` | OSINT and cybersecurity sources — Shodan, Censys, VirusTotal, HaveIBeenPwned, Whoxy, Hunter, Social Searcher, Jobs Boards | Hidden in a collapsible "Advanced — Cybersecurity & OSINT" panel, unchecked by default |

Advanced sources require API keys and are intended for threat intelligence and digital forensics workflows.

**Agent Pattern:**
```python
class BaseCollector(ABC):
    async def collect(self, query: str) -> list[Document]:
        """Implement per agent type."""
        pass
    
    async def validate_credentials(self) -> bool:
        """Return True if ready, False if skipped."""
        pass
```

**Execution Model:**
- All collectors run in parallel via `asyncio.gather()`
- Each returns a `Document` list
- Failed collectors are silently skipped (graceful degradation)
- Results combined in aggregator

### 2.3 **Processing Pipeline (`aria/processing/` / `aria/brain/`)**

Data transformation and cleaning engine.

**Key Components:**

| Module | Purpose |
|--------|---------|
| **`expander.py`** | Query expansion: 1 topic → 5–8 diverse queries |
| **`cleaner.py`** | Smart cleaning: LLM auto-detects content type + extracts |
| **`router.py`** | Route content to correct extraction strategy |
| **`translator.py`** | Multi-language detection and translation |
| **`extractor.py`** | Content-type-specific extraction logic |

**Smart Cleaning Strategy (10 types auto-detected):**

| Content Type | Extracted Fields | LLM Cost |
|---|---|---|
| `academic_paper` | Research question, methodology, findings, limitations | 1 call |
| `news_article` | Who/what/when/where/why, quotes, sources | 1 call |
| `forum_post` | Question, consensus answer, vote score | 1 call |
| `social_media` | Core claim, evidence, credibility signals | 1 call |
| `technical_doc` | Concept, instructions, code, version | 1 call |
| `video_transcript` | Key points, examples, speaker conclusions | 1 call |
| `encyclopedia` | Definition, key facts, related concepts | 1 call |
| `opinion_essay` | Thesis, evidence, counter-arguments | 1 call |
| `gov_policy` | Policy name, date, affected parties, penalties | 1 call |
| `data_report` | Headline stats, trends, source, methodology | 1 call |

**Deduplication Strategy:**
1. **URL-level dedup:** Exact URL match → skip
2. **Content fingerprint:** MD5(normalized_text) → skip if seen before
3. **Threshold:** Only keep if >70% unique content (configurable)

### 2.4 **Storage Layer (`aria/storage/`)**

Persistent document store with dual schema (raw + cleaned).

**Schema Structure:**

```
raw_documents/
├── source_name/
│   ├── source_type.jsonl    # One JSON per line
│   └── index.json           # Metadata index

cleaned_documents/
├── source_name/
│   ├── extracted.jsonl      # Cleaned, structured
│   └── index.json           # Lookup table
```

**Document Schema (Raw):**
```json
{
  "id": "uuid",
  "url": "https://...",
  "source": "arxiv",
  "source_type": "academic",
  "title": "...",
  "raw_content": "...",
  "metadata": {
    "fetch_time": 1234567890,
    "http_status": 200,
    "language": "en"
  },
  "hash": "md5(...)"
}
```

**Document Schema (Cleaned):**
```json
{
  "id": "uuid",
  "raw_id": "uuid_of_raw",
  "content_type": "academic_paper",
  "extracted": {
    "research_question": "...",
    "methodology": "...",
    "findings": "...",
    "limitations": "..."
  },
  "relevance_score": 0.85,
  "quality_flags": ["..."],
  "processing_metadata": {
    "cleaned_at": 1234567890,
    "llm_model": "claude-3.5-sonnet",
    "tokens_used": 1250
  }
}
```

### 2.5 **Export Layer (`aria/export/`)**

Multi-format output generation with pluggable formatters.

**Supported Formats:**

| Format | Content | Use Case |
|--------|---------|----------|
| **JSON** | Raw + cleaned, full metadata | API consumption, downstream processing |
| **CSV** | Tabular (one row per doc, selected fields) | Excel, analytics tools |
| **Markdown** | Formatted report with relevance sorting | Human reading, wikis, GitHub |
| **HTML** | Interactive web report; sortable, searchable | Browser viewing, sharing |
| **ZIP** | All 5 formats + raw data dump | Complete archive |
| **PDF** | Formatted report (via HTML rendering) | Print, distribution |

**Exporter Architecture:**
```python
class BaseFormatter(ABC):
    def format(self, documents: list[Document], metadata: dict) -> str:
        """Generate output in specific format."""
        pass

class JSONFormatter(BaseFormatter):
    def format(self, documents, metadata):
        return json.dumps(...)

class CSVFormatter(BaseFormatter):
    def format(self, documents, metadata):
        return "\n".join([...])
```

### 2.6 **API Layer (`aria/api/`)**

FastAPI microservice for async research execution and result retrieval.

**Routes:**

| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/health` | GET | Health check |
| `/runs` | POST | Start new research run |
| `/runs/{run_id}` | GET | Poll run status |
| `/runs/{run_id}/cancel` | POST | Cancel active run |
| `/exports/{run_id}` | GET | Download results in specified format |
| `/missions` | GET | List available missions |
| `/missions` | POST | Upload new mission config |
| `/credentials` | GET | List configured credentials |
| `/credentials` | POST | Store/update credential |

**Run Lifecycle:**
```
POST /runs → pending
    ↓
→ collecting (phase 1)
    ↓
→ cleaning (phase 2)
    ↓
→ completed (phase 3)
    ↓
GET /exports → download results
```

**Authentication:** Credential registry with environment variable fallback

### 2.7 **Access Control (`aria/access/`)**

Credential management and session handling.

**Credential Types:**
- API keys (OpenAI, OpenRouter, etc.)
- OAuth tokens (Twitter, LinkedIn, GitHub)
- Session cookies (institutional access)
- User/pass pairs (LinkedIn via Playwright)
- Local app connections (Zotero desktop)

**Strategy:**
1. Check `aria.config.Credentials` object (in-memory)
2. Fall back to environment variables
3. If neither: skip this source (graceful degradation)

### 2.8 **LLM Ensemble (`aria/agents/llm_ensemble.py`)**

Multi-provider LLM abstraction layer.

**Supported Providers:**

| Provider | Models Available | Config |
|----------|---|---|
| **OpenRouter** | 100+ (meta-provider) | API key |
| **OpenAI** | GPT-4, GPT-3.5, etc. | API key |
| **Anthropic** | Claude 3 family, Claude 2 | API key |
| **Ollama** | llama3.1, llama3.2, mistral, etc. | Local URL |

**Selection Modes:**
1. **Single model:** Use specified provider/model
2. **Ensemble mode:** Call multiple models in parallel, take majority vote or weighted score
3. **Cascade mode:** Try model 1; if rate-limited, try model 2, etc.

**Usage in Cleaning:**
```python
response = await llm_ensemble.call(
    provider="openrouter",
    model="meta-llama/llama-2-70b",
    prompt=cleaning_prompt,
    temperature=0.2,  # Deterministic extraction
)
```

### 2.9 **Configuration (`aria/config.py`)**

Environment and mission-based configuration.

**Config Sources (priority order):**
1. CLI arguments (`--topic`, `--mission`, etc.)
2. Mission YAML file
3. Environment variables
4. Defaults from code

**Key Config Options:**
```python
@dataclass
class Config:
    topic: str
    depth_level: int = 2  # 1-5: Surface to Maximum
    sources: list[str] = field(default_factory=lambda: ["web", "academic"])
    llm_provider: str = "openrouter"
    llm_model: str = "meta-llama/llama-2-70b"
    enable_dedup: bool = True
    enable_cleaning: bool = True
    export_formats: list[str] = field(default_factory=lambda: ["json", "csv"])
    max_documents: int = 500
    timeout_seconds: int = 3600
```

---

## 3. Data Flow Example: End-to-End

### Scenario: User researches "AI safety benchmarks 2025"

```
1. CLI Entry
   $ python -m aria.cli --topic "AI safety benchmarks 2025" --mission missions/examples/default.yaml

2. Config Load
   - Load mission YAML
   - Merge with CLI args
   - Validate config
   - Load credentials from env

3. Query Expansion (Phase 1)
   - LLM expands: "AI safety benchmarks 2025"
   - → [
       "AI safety evaluation metrics 2025",
       "benchmark datasets for LLM safety",
       "safety testing frameworks for language models",
       "AI alignment research benchmarks",
       "large language model safety standards 2024 2025"
     ]

4. Parallel Collection (Phase 2)
   asyncio.gather(
     web_agent.collect(expanded_queries),
     academic_agent.collect(expanded_queries),
     youtube_agent.collect(expanded_queries),
     reddit_agent.collect(expanded_queries),
     ...
   )
   - 18 agents fire simultaneously
   - Each returns Document[] or []
   - Total ~200-500 documents collected (depends on depth)

5. Aggregation & Dedup (Phase 3)
   - Merge all documents
   - URL-level dedup: Remove exact duplicates
   - Content fingerprint dedup: Remove similar content
   - Result: ~180-450 unique documents

6. Smart Cleaning (Phase 4)
   - For each document:
     1. LLM auto-detects type
     2. Extract relevant fields
     3. Compute relevance_score (0-1)
     4. Store cleaned + metadata
   - Total LLM cost: N documents × 1 call = N API calls

7. Export (Phase 5)
   - User selects format: JSON, CSV, Markdown, HTML
   - Generate and save to data/exports/
   - Ready for download

8. Storage
   data/
   ├── raw/
   │   ├── web/
   │   │   └── search.jsonl
   │   ├── academic/
   │   │   ├── arxiv.jsonl
   │   │   ├── pubmed.jsonl
   │   │   └── semantic_scholar.jsonl
   │   └── ...
   └── clean/
       ├── web/
       │   └── extracted.jsonl
       ├── academic/
       │   └── extracted.jsonl
       └── ...
```

---

## 4. Parallel Execution Model

### 4.1 Asyncio-based Concurrency

All I/O-bound operations (HTTP, DB, LLM calls) use **asyncio**:

```python
async def orchestrate(mission: Mission):
    # Phase 1: Query expansion
    expanded = await query_expander.expand(mission.topic)
    
    # Phase 2: Parallel collection (all 18 agents simultaneously)
    results = await asyncio.gather(
        web_agent.collect(expanded),
        academic_agent.collect(expanded),
        youtube_agent.collect(expanded),
        # ... 15 more agents
        return_exceptions=True  # Don't crash if one fails
    )
    
    # Phase 3: Aggregate
    documents = aggregator.merge(results)
    
    # Phase 4: Parallel cleaning (batch LLM calls)
    cleaned = await asyncio.gather(
        *[cleaner.clean(doc) for doc in documents],
        return_exceptions=True
    )
    
    # Phase 5: Export
    exporter.export(cleaned, formats=mission.export_formats)
```

### 4.2 Rate Limiting & Backoff

**Global Rate Limiter:**
- Per-provider rate limits (e.g., OpenAI: 90k TPM)
- Exponential backoff on 429 (Too Many Requests)
- Token-aware batching for LLM calls

**Per-Source Rate Limits:**
- Respect `robots.txt` for web scrapers
- Honor API rate limit headers
- Jitter to avoid thundering herd

---

## 5. LLM Integration Architecture

### 5.1 Cleaning Prompt Template

```
You are a research content analyzer. 
Analyze the following document and extract structured information.

First, determine the content type from these categories:
1. academic_paper
2. news_article
3. forum_post
4. social_media
5. technical_doc
6. video_transcript
7. encyclopedia
8. opinion_essay
9. gov_policy
10. data_report

Document:
---
{document_text}
---

Respond in JSON:
{
  "content_type": "...",
  "extracted_fields": {
    // type-specific fields
  },
  "relevance_score": 0.0-1.0,
  "quality_flags": [...]
}
```

### 5.2 Model Selection

**Default Chain:**
```
User selects model
    ↓
Model available? → Yes → Use it
    ↓ No
    ↓
Try fallback model
    ↓
Try alternative provider
    ↓
Skip document (log warning)
```

---

## 6. Error Handling & Resilience

### 6.1 Failure Modes

| Scenario | Handling |
|----------|----------|
| Agent timeout | Skip source, log warning, continue |
| API rate limit | Exponential backoff + queue retry |
| LLM API error | Skip cleaning step, return raw doc |
| Invalid mission YAML | Raise error, exit |
| Storage write fail | Retry 3×, then fail run |
| Credential missing | Skip source, log as "skipped" |
| Dedup collision | Merge metadata, keep higher relevance |

### 6.2 Retry Strategy

```
def retry_with_backoff(func, max_retries=3, base_delay=1):
    for attempt in range(max_retries):
        try:
            return await func()
        except RateLimitError:
            delay = base_delay * (2 ** attempt) + random.jitter()
            await asyncio.sleep(delay)
        except Exception as e:
            if attempt == max_retries - 1:
                raise
            # Log and continue
```

---

## 7. Scalability Considerations

### 7.1 Horizontal Scaling

- **Stateless agents:** Each collector can run on separate worker
- **Message queue:** Use Redis/RabbitMQ for task distribution
- **Distributed cleaning:** Batch documents across multiple cleaning workers

### 7.2 Storage Optimization

- **Compression:** gzip raw documents before archiving
- **Indexing:** SQLite/PostgreSQL for metadata lookup
- **Partitioning:** Store documents by date/source for faster queries

### 7.3 Cost Control

- **Token tracking:** Count tokens per LLM call, alert on budget
- **Provider switching:** Automatically try cheaper provider on error
- **Batch inference:** Combine multiple documents in one LLM call

---

## 8. Frontend Integration

### 8.1 API Contracts

**Start Research:**
```bash
POST /api/runs
{
  "topic": "AI safety benchmarks 2025",
  "mission_id": "default",
  "depth_level": 2
}
→ { "run_id": "abc-123", "status": "pending" }
```

**Poll Status:**
```bash
GET /api/runs/abc-123
→ { "status": "collecting", "progress": 0.45, "documents_collected": 90 }
```

**Export Results:**
```bash
GET /api/exports/abc-123?format=json
→ [file download]
```

### 8.2 Frontend Responsibilities

- Display real-time progress (via polling or WebSocket)
- Format export options dropdown
- Render results dashboard
- Handle credential input UI
- Mission template selection

---

## 9. Technology Stack

| Component | Technology | Notes |
|-----------|-----------|-------|
| **Language** | Python 3.11+ | Type hints, async/await |
| **API Framework** | FastAPI | Async, auto-OpenAPI, WebSocket support |
| **Async Runtime** | asyncio | Built-in, no extra deps |
| **Web Scraping** | BeautifulSoup, Playwright | HTML parsing + headless browser |
| **HTTP Client** | aiohttp, httpx | Async HTTP |
| **LLM Client** | LiteLLM, OpenRouter SDK | Multi-provider abstraction |
| **Storage** | File system (JSONL) + optional SQLite | Local development; PostgreSQL for production |
| **Config** | YAML (mission) + dataclass (code) | Mission-driven + env-based |
| **CLI** | Click or argparse | Entry point for headless execution |
| **Frontend** | Flutter (aria_studio) or web (aria-report) | Separate UI layer |
| **Testing** | pytest, pytest-asyncio | Unit + integration tests |
| **Logging** | Python logging | Structured logs for debugging |

---

## 10. Deployment Architecture

### 10.1 Development

```
User runs locally:
  python -m aria.cli --serve-api
  → API starts on http://localhost:8000
  → Flutter/web app connects to localhost
```

### 10.2 Production

```
Docker container:
  - FastAPI server in container
  - PostgreSQL for storage
  - Redis for rate limiting + task queue
  - Kubernetes deployment for scaling
  - S3 for export archive storage
```

### 10.3 CI/CD

- Tests on every PR
- Type checking (mypy)
- Linting (flake8, black)
- Security scanning
- Docker image build + push

---

## 11. Security Considerations

1. **Credential Isolation:** Never log API keys; store in env vars or secure vault
2. **Rate Limiting:** Prevent abuse via global + per-IP limits
3. **Input Validation:** Validate mission YAML against schema
4. **HTTPS Only:** Production API must use TLS
5. **CORS:** Restrict frontend origins
6. **Access Control:** Basic auth or JWT for API endpoints

---

## 12. Future Roadmap

- [ ] Distributed worker pool for scaling
- [ ] PostgreSQL storage with full-text search
- [ ] WebSocket live progress updates
- [ ] Custom extraction template builder
- [ ] Webhook notifications on completion
- [ ] Caching layer for repeated queries
- [ ] GraphQL API option
- [ ] Browser extension for quick research capture

---

## Appendix: Module Dependencies

```
cli.py
  → config.py, mission.py, orchestrator/master.py

orchestrator/master.py
  → sources/*, processing/*, storage/*, export/*, access/manager.py

sources/* (all collectors)
  → types/document.py, utils/*, access/manager.py

processing/cleaner.py
  → agents/llm_ensemble.py, types/document.py

export/exporter.py
  → export/formatters/*, storage/*

api/app.py
  → orchestrator/*, storage/*, access/*, FastAPI, pydantic
```

---

**Last Updated:** April 2026  
**Architecture Version:** 5.0.0
