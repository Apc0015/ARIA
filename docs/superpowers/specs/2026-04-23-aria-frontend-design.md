# ARIA Frontend — Design Spec

**Date:** 2026-04-23
**Status:** Approved
**Target:** `aria-report/` (React + Vite + Tailwind scaffold)

---

## 1. Overview

Full production web app for ARIA. Users log in, launch research runs, monitor live progress, view completed reports, manage source connectors, and configure credentials. Replaces the blank Vite scaffold in `aria-report/`.

**Not** a marketing page. This is the live tool.

---

## 2. Visual Design

### Theme: Glass Depth

CSS 3D perspective creates physical depth without WebGL. All surfaces are glassmorphic — semi-transparent, layered, with specular edge highlights. Darkness is the canvas; content emerges from it.

Follows `docs/DESIGN.md` (Linear-inspired system) exactly:
- **Background:** `#08090a` (page), `#0f1011` (sidebar/panels), `#191a1b` (elevated surfaces)
- **Text:** `#f7f8f8` primary, `#d0d6e0` secondary, `#8a8f98` muted, `#62666d` de-emphasized
- **Accent:** `#5e6ad2` CTA backgrounds, `#7170ff` interactive accents, `#828fff` hover
- **Borders:** `rgba(255,255,255,0.08)` standard, `rgba(255,255,255,0.05)` subtle
- **Status:** `#10b981` success/done, `#7170ff` running/active
- **Typography:** Inter Variable with `font-feature-settings: "cv01", "ss03"` globally

### 3D / Motion System

| Effect | Technique | Where |
|--------|-----------|-------|
| Card depth | `perspective(400px) rotateX(2–4deg)` + top-edge specular gradient | Stat cards, run rows, source cards |
| Card hover | `translateY(-3px)`, perspective flattens | All interactive cards |
| Page transitions | Framer Motion `x: 20→0, opacity: 0→1, duration: 0.2s` | All route changes |
| Staggered entrance | Framer Motion `staggerChildren: 0.05s` | Card grids on page load |
| Live counter | Framer Motion spring number ticker | Doc count in Monitor, stat cards |
| Progress bars | Framer Motion `scaleX` spring | Monitor per-source bars |
| Active glow | CSS `box-shadow` pulse animation | Running status dots, active source |
| Ambient spotlight | Slow radial gradient shift on nav change | Page background |

---

## 3. App Shell

### Layout

```
┌──────────────────────────────────────────────────────┐
│  56px sidebar  │  topbar (44px)                       │
│                ├──────────────────────────────────────│
│  icon rail     │  content area (scrolls)              │
│                │                                      │
│  [logo]        │                                      │
│  [dashboard]   │                                      │
│  [launch]      │                                      │
│  [monitor]     │                                      │
│  [reports]     │                                      │
│  [sources]     │                                      │
│  ──────        │                                      │
│  [settings]    │                                      │
└──────────────────────────────────────────────────────┘
```

### Sidebar (`AppSidebar`)
- 56px wide, `#0f1011` background, right border `rgba(255,255,255,0.06)`
- ARIA logomark at top (gradient `#5e6ad2 → #7170ff`, 32×32px, 8px radius)
- Icon items: 36×36px, 8px radius, hover `rgba(255,255,255,0.04)`, active `rgba(113,112,255,0.15)` + left 2px `#7170ff` indicator bar
- Tooltips: appear on hover, `#191a1b` bg, `1px solid rgba(255,255,255,0.1)`, 6px radius
- Settings icon pinned to bottom
- Mobile (< 768px): sidebar collapses to bottom tab bar (5 primary tabs)

### Topbar (`PageTopbar`)
- 44px tall, per-page, `border-bottom: 1px solid rgba(255,255,255,0.05)`
- Left: breadcrumb (page name, optional sub-item)
- Center/right: ⌘K search trigger + context-specific action button (e.g. "+ New Run" on Dashboard)

---

## 4. Pages

### 4.1 Dashboard (`/`)

**Purpose:** Home screen — current state at a glance + quick launch.

**Layout (top to bottom):**
1. **Stats strip** — 4 glass cards in a row:
   - Total Runs, Docs Collected, Active Now, Sources Connected
   - Each: `perspective(400px) rotateX(2deg)`, specular top highlight, delta line in green/violet
2. **Quick Launch bar** — full-width glass panel:
   - Text input: "Enter research topic or paste mission YAML…"
   - Source pill toggles (Web, arXiv, Social, Media) — active pill in violet
   - `▶ Launch` CTA button (`#5e6ad2`, glow shadow)
   - On submit: navigates to `/monitor/:runId`
3. **Recent Runs list** — scrollable rows:
   - Left 2px status bar (violet=running, green=done, dim=queued)
   - Animated status dot (pulsing for running)
   - Topic name, source tags, doc count, relative time
   - Click row → `/report/:runId`
   - "View all runs →" link at bottom

### 4.2 Run Launcher (`/launch`)

**Purpose:** Configure and start a new research run.

**Layout:**
1. **Topic input** — large text area, prominent
2. **Mission YAML** — expandable panel: paste or upload `.yaml` file
3. **Source selector grid** — 4-column card grid (Web / Academic / Social / Media categories):
   - Each source as a toggle card: icon, name, enable/disable
   - Disabled if no credentials configured (shows "Configure →" link to Settings)
4. **Configuration panel** — collapsible:
   - Max docs per source (slider)
   - Parallel workers (select)
   - Output format checkboxes (PDF, HTML, JSON)
5. **Launch button** — full-width `#5e6ad2`, with estimated time preview
6. On launch: POST to `POST /api/runs`, redirect to `/monitor/:runId`

### 4.3 Live Monitor (`/monitor/:runId`)

**Purpose:** Real-time view of an in-progress run.

**Layout:**
1. **Header** — run topic, elapsed time, overall progress bar (Framer Motion `scaleX`)
2. **Per-source pipeline** — grid of source cards:
   - Each shows: source name, icon, status (queued/collecting/done/error), doc count (ticking counter), progress bar
   - Active cards pulse with violet glow
3. **Document stream** — live scrolling list of newest docs as they arrive (polling `GET /api/runs/:id/docs?limit=20`)
4. **Log stream** — collapsible panel, raw log lines
5. **ETA strip** — estimated completion, docs/min rate
6. Polls `GET /api/runs/:id` every 3s via TanStack Query. Auto-redirects to `/report/:runId` on completion.

### 4.4 Run Report (`/report/:runId`)

**Purpose:** View a completed run's full output.

**Layout:**
1. **Summary panel** — glass card:
   - Topic, completion time, total docs, sources used
   - Export buttons: PDF, HTML, JSON (calls `GET /api/runs/:id/export?format=pdf` etc.)
2. **Source breakdown** — horizontal bar chart or pill row showing docs per source
3. **Documents table** — paginated, sortable:
   - Columns: Title, Source, URL, Date, Score
   - Row click → doc detail slide-over panel
4. **Re-run button** — launches `/launch` pre-filled with same config

### 4.5 Sources (`/sources`)

**Purpose:** Enable/disable the 20 source connectors.

**Layout:**
1. **Category tabs** — Web / Academic / Social / Media
2. **Connector grid** — cards per source:
   - Icon, name, description
   - Toggle switch (enabled/disabled)
   - Credential status badge: "Configured ✓" or "Not configured"
   - "Configure credentials →" links to Settings > Connections
3. Reads from `GET /api/sources`, PATCHes enable state

### 4.6 Settings (`/settings`)

**Purpose:** Global configuration including all connector credentials.

**Sections (left nav within the page):**

1. **Connections** *(primary section)*
   - Full list of all 20 connectors grouped by category (Web, Academic, Social, Media)
   - Each connector: expandable row showing required fields (API key, token, username, etc.)
   - Status indicator: configured / partial / not configured
   - "Test connection" button per connector
   - Save per-connector or bulk save
   - Connectors: Reddit (client_id + secret), Twitter/X (bearer_token), LinkedIn (token), Slack (bot_token), arXiv (no auth), PubMed (api_key), Semantic Scholar (api_key), YouTube (api_key), Vimeo (access_token), Podcast (none), Medium (no auth), Dev.to (api_key), HackerNews (no auth), Substack (no auth), RSS (no auth), Wikipedia (no auth), GitHub (token), PDF (no auth), Search (api_key), Government (no auth)

2. **Default Mission**
   - Paste/upload default mission YAML used when launching without one

3. **Output**
   - Default export formats (checkboxes: PDF / HTML / JSON)
   - Output directory path (for CLI integration)

4. **Appearance**
   - (Reserved) Dark mode only for now — no toggle needed

---

## 5. API Integration

All pages talk to the existing ARIA FastAPI backend.

| Page | Endpoints used |
|------|---------------|
| Dashboard | `GET /api/runs?limit=10` (stats derived client-side from run list) |
| Launcher | `GET /api/credentials` (to show configured status), `POST /api/runs` |
| Monitor | `GET /api/runs/{run_id}` (poll 3s), `GET /api/runs/{run_id}/documents` (poll 3s) |
| Report | `GET /api/runs/{run_id}`, `GET /api/runs/{run_id}/documents`, export endpoints below |
| Sources | Source list hardcoded in frontend (20 connectors from registry); `GET /api/credentials` for status |
| Settings | `GET /api/credentials`, `POST /api/credentials` |

**Export endpoints (Report page):**
- `GET /api/runs/{run_id}/export/markdown` — Markdown report
- `GET /api/runs/{run_id}/export/clean/json` — Clean JSON
- `GET /api/runs/{run_id}/export/clean/csv` — CSV
- `GET /api/runs/{run_id}/export/raw` — Raw collected docs

**Note:** `GET /api/stats` does not exist. Dashboard stats (total runs, total docs, active count, sources connected) are computed client-side from the runs list and credentials response. No new backend endpoint needed.

TanStack Query handles all fetching, caching, and polling. No manual `useEffect` fetch logic.

---

## 6. Tech Stack

| Package | Version | Role |
|---------|---------|------|
| React | 18 | UI (existing) |
| Vite | 5 | Build (existing) |
| Tailwind CSS | 3 | Styling (existing) |
| React Router | v6 | Client routing |
| Framer Motion | 11 | Animations + transitions |
| TanStack Query | v5 | Data fetching + polling |
| TypeScript | 5 | Type safety |

No Three.js, no WebGL, no heavy 3D libraries.

---

## 7. File Structure

```
aria-report/src/
├── main.tsx                  Router setup, QueryClientProvider
├── App.tsx                   Root layout (sidebar + outlet)
├── components/
│   ├── layout/
│   │   ├── AppSidebar.tsx
│   │   └── PageTopbar.tsx
│   ├── ui/
│   │   ├── GlassCard.tsx     Base glass card with CSS 3D
│   │   ├── StatusDot.tsx     Animated status indicator
│   │   ├── SourcePill.tsx    Source tag pill
│   │   └── NumberTicker.tsx  Framer Motion spring counter
│   └── shared/
│       └── RunRow.tsx        Reusable run list row
├── pages/
│   ├── Dashboard.tsx
│   ├── Launch.tsx
│   ├── Monitor.tsx
│   ├── Report.tsx
│   ├── Sources.tsx
│   └── Settings.tsx
├── hooks/
│   ├── useRun.ts             TanStack Query for single run
│   ├── useRuns.ts            TanStack Query for run list
│   └── useSources.ts         TanStack Query for sources
├── lib/
│   └── api.ts                Typed fetch wrappers
└── styles/
    └── globals.css           CSS variables, 3D utilities, animations
```

---

## 8. Responsive Behavior

| Breakpoint | Change |
|-----------|--------|
| < 768px | Sidebar collapses to bottom tab bar (5 primary pages) |
| < 640px | Stats strip goes 2×2 grid, launch bar stacks vertically |
| < 480px | Source grid goes single column |

---

## 9. What Gets Removed

- `aria-report/src/App.tsx` — replace entirely (currently blank scaffold)
- `aria-report/src/App.css` — replace with globals.css
- `aria-report/src/assets/` — remove Vite/React placeholder assets
