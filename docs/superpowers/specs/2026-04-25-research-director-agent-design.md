# Research Director Agent — Design Spec

**Date:** 2026-04-25
**Status:** Approved
**Author:** Ayush Chhoker

---

## Problem

The current query planner (`aria/engine/intelligence/query_planner.py`) makes one LLM call with a generic template and produces 20 keyword queries regardless of topic type, user intent, or audience. It treats every topic identically.

A world-class human researcher does the opposite — they think deeply about what they are looking for, who they are researching for, and what order to search in before touching any search engine.

---

## Goal

Replace the single-shot query planner with a **Research Director Agent** that:

1. Talks to the user to understand context before searching
2. Builds a rich Research Brief from that conversation
3. Drives phased, ordered collection instead of one giant parallel blast

---

## Architecture

```
User types topic
        ↓
┌─────────────────────────────────────┐
│        Research Director Agent      │
│                                     │
│  1. Disambiguate topic              │
│  2. Ask clarifying questions (loop) │
│  3. Build Research Brief            │
│  4. Generate Phased Plan            │
└─────────────────────────────────────┘
        ↓  Research Brief + Phased Plan
┌─────────────────────────────────────┐
│        Existing ARIA Pipeline       │
│                                     │
│  Phase 1: Landscape collection      │
│  Phase 2: Deep dive per question    │
│  Phase 3: Critical / counter-args   │
│  Phase 4: Latest developments       │
└─────────────────────────────────────┘
        ↓
     Cleaned + scored results
```

**What changes:** `query_planner.py` replaced by `research_director.py`
**What stays the same:** All 37 collectors, LLM cleaning, gap detection, export system

---

## New Files

```
aria/engine/intelligence/
├── research_director.py     ← main agent (replaces query_planner.py)
├── research_brief.py        ← ResearchBrief dataclass
├── phased_planner.py        ← converts brief → phased collection plan
└── query_planner.py         ← kept as fallback (no LLM available)
```

---

## Section 1 — Clarifying Conversation Flow

### Rules

- Questions asked **one at a time**
- Every question has a **skip option**
- User can type **"start"** at any point to stop questions immediately
- Maximum **10 questions total** — never exceeds this
- If user **skips 3 in a row** → stop asking, start with available info
- Next question is **dynamic** — depends on previous answer

### Question Categories (in order)

```
1. Disambiguation     — what does this topic actually mean?
2. Audience           — who is this research for?
3. Purpose            — why are they researching this?
4. Angle/Focus        — what specific aspect matters most?
5. Time range         — historical, recent, or latest only?
6. Geography          — global or specific region?
7. Depth              — surface overview or deep expert-level?
8. Format preference  — academic papers, news, practical guides?
9. What to exclude    — anything they explicitly don't want?
10. Final check       — anything else before we start?
```

### Example Conversation

```
User:  "depression"

ARIA:  "This topic could mean different things. Which do you mean?
        1. Mental health condition
        2. Economic recession/downturn
        3. Something else?"

User:  "mental health"

ARIA:  "Who is this research for?
        1. General understanding (student/curious person)
        2. Medical/clinical professional
        3. Academic researcher
        4. Someone personally affected
        (or skip)"

User:  "skip"

ARIA:  "What specific angle interests you most?
        1. Causes and risk factors
        2. Treatment options
        3. Latest research breakthroughs
        4. Global statistics
        5. All angles equally
        (or skip)"

User:  "treatment options"

ARIA:  "Any time range preference?
        1. Latest only (2024-2026)
        2. Last 5 years
        3. All time including historical
        (or skip)"

User:  "skip"

ARIA:  "Got everything I need. Starting research now..."
```

---

## Section 2 — Research Brief

After conversation ends, Research Director builds a `ResearchBrief` internally:

### ResearchBrief Structure

```python
@dataclass
class ResearchBrief:
    # Core
    original_topic: str          # "depression"
    resolved_topic: str          # "mental health depression — treatment options"
    
    # Context (from conversation or inferred)
    audience: str                # "general public (inferred)"
    purpose: str                 # "informational"
    depth: str                   # "medium"
    time_range: str              # "all time"
    geography: str               # "global"
    language: str                # "english"
    
    # Research strategy
    key_questions: list[str]     # 5-10 specific questions to answer
    entities: list[str]          # key people, orgs, concepts to find
    ambiguities_resolved: list[str]  # what was clarified
    
    # Source strategy
    must_have_sources: list[str] # ["academic", "clinical_trials"]
    skip_sources: list[str]      # ["github", "youtube"]
    
    # Collection plan
    phases: list[ResearchPhase]  # ordered phases
```

### How Brief is Built

- Answers from conversation → fill known fields
- Skipped questions → LLM infers reasonable defaults based on topic + available context
- `key_questions` → LLM generates 5-10 specific research questions from resolved topic
- `entities` → LLM extracts key entities (people, orgs, concepts, drugs, companies)
- `source_strategy` → determined by topic type + audience + purpose

---

## Section 3 — Phased Collection Plan

Collection runs in **4 ordered phases** instead of one parallel blast.

### Phase Definitions

```
Phase 1 — LANDSCAPE
  Goal:     Understand the big picture first
  Queries:  Broad overview of resolved topic
  Sources:  Wikipedia, web search, general news
  Max docs: 50
  Output:   Feeds entity list into Phase 2

Phase 2 — DEEP DIVE
  Goal:     Answer each key_question specifically
  Queries:  One query cluster per key_question
  Sources:  Academic, clinical trials, technical docs
  Max docs: 150
  Output:   Feeds gaps into Phase 3

Phase 3 — CRITICAL
  Goal:     Find counter-arguments, risks, failures
  Queries:  topic + "criticism", "risks", "failure", "side effects"
  Sources:  Academic, news, government
  Max docs: 50
  Output:   Feeds time-sensitive gaps into Phase 4

Phase 4 — LATEST
  Goal:     Find newest developments only
  Queries:  topic + current year, "breakthrough", "new study", "2025", "2026"
  Sources:  arXiv, medical journals, news
  Max docs: 50
```

### Why Phases Beat One Big Blast

```
OLD: Fire all 37 collectors → 500 random docs → AI guesses relevance

NEW: Phase 1 results teach Phase 2 what to search for
     Phase 2 results reveal gaps for Phase 3
     Phase 3 reveals time-sensitive gaps for Phase 4
     Result: 300 highly targeted documents
```

### UI Display

```
[Phase 1] Understanding landscape...       ✓ 45 docs
[Phase 2] Deep diving key questions...     ✓ 132 docs
[Phase 3] Finding counter-arguments...     ✓ 38 docs
[Phase 4] Latest developments...           ✓ 41 docs
──────────────────────────────────────────────────────
Total: 256 targeted documents
```

---

## Section 4 — Integration Points

### API Changes

`POST /api/runs` gains new flow:

```
1. Request arrives with topic
2. Research Director starts conversation (WebSocket or polling)
3. Frontend shows question → user answers → next question
4. User clicks "Start Research" or says "start"
5. Brief built → phased plan generated
6. Normal collection pipeline starts with phased plan
```

### Mission YAML Support

```yaml
# Disable conversation (for automated/API use)
research_director:
  enabled: true
  interactive: false    # skip questions, use LLM inference only
  max_questions: 10

# Or pre-fill context to skip questions
research_context:
  audience: "medical professional"
  purpose: "clinical research"
  depth: "expert"
  time_range: "last 5 years"
```

### Fallback Behavior

```
No LLM available → skip Research Director → use existing heuristic query_planner.py
LLM available, user skips all → build brief from topic alone via LLM inference
API/automated mode → interactive: false → LLM infers all context silently
```

---

## Section 5 — Data Flow

```
topic (string)
    ↓
ResearchDirector.start_conversation(topic)
    ↓ yields questions one at a time
    ← user answers (or skips)
ResearchDirector.build_brief(topic, answers)
    ↓ one LLM call to fill in gaps + generate key_questions + entities
ResearchBrief (dataclass)
    ↓
PhasedPlanner.generate_phases(brief)
    ↓ produces 4 ResearchPhase objects with targeted queries
    ↓
InfoCollectorOrchestrator.run_phased(phases)
    ↓ runs existing collectors phase by phase
    ↓
Results (cleaned, scored, exported as normal)
```

---

## Section 6 — Error Handling

| Scenario | Behaviour |
|---|---|
| LLM unavailable | Skip Director → fallback to `query_planner.py` heuristic |
| User skips all questions | Build brief from topic only via LLM inference |
| Ambiguous topic, user skips disambiguation | Research all interpretations, tag docs by interpretation |
| API/CLI mode (no interactive terminal) | `interactive: false` → LLM infers all context silently |
| Phase 1 returns 0 docs | Skip to Phase 2 with broadened queries |
| Phase fails mid-run | Log warning, continue with remaining phases |

---

## Section 7 — Files to Create / Modify

| File | Action | Description |
|---|---|---|
| `aria/engine/intelligence/research_director.py` | CREATE | Main agent — conversation loop + brief builder |
| `aria/engine/intelligence/research_brief.py` | CREATE | ResearchBrief + ResearchPhase dataclasses |
| `aria/engine/intelligence/phased_planner.py` | CREATE | Converts brief → 4-phase collection plan |
| `aria/engine/orchestrator/core.py` | MODIFY | Call ResearchDirector before collection, run phased |
| `aria/api/routes/runs.py` | MODIFY | Add WebSocket/SSE endpoint for question stream |
| `aria-report/src/pages/Launch.tsx` | MODIFY | Show conversation UI before progress bar |
| `aria/engine/intelligence/query_planner.py` | KEEP | Fallback only — no changes |

---

## Success Criteria

- [ ] User types any topic → gets asked smart clarifying questions
- [ ] Skip works at every question
- [ ] "start" command stops questions immediately
- [ ] 3 consecutive skips stops questions automatically
- [ ] Research Brief correctly captures all user answers + infers missing context
- [ ] 4 phases run in order, each informed by previous phase results
- [ ] Existing runs (no Research Director) still work via fallback
- [ ] Automated/API mode works with `interactive: false`
- [ ] Results are noticeably more targeted than current output
