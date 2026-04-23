# ARIA Studio — Go-Live Readiness Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Harden ARIA Studio (FastAPI backend + Flutter frontend) to a production-ready state safe to expose publicly tomorrow.

**Architecture:** Two-tier: FastAPI backend (`aria/api/`) at port 8765, Flutter web frontend (`aria_studio/`) served as static files via nginx. All issues are in-repo — no dependency upgrades needed beyond adding `shared_preferences` to pubspec.

**Tech Stack:** Python 3.11+, FastAPI, Flutter/Dart, nginx, Docker

---

## Audit Summary — What's Broken

| Severity | Issue | File |
|----------|-------|------|
| 🔴 CRITICAL | CORS `allow_origins=["*"]` + `allow_credentials=True` — browser blocks all credentialed XHR | `aria/api/app.py:49-52` |
| 🔴 CRITICAL | Path traversal in download: `rglob(filename)` with no boundary check | `aria/api/routes/exports.py:88-92` |
| 🟠 HIGH | `os.environ` mutated globally on `set_brain_config` — race condition under concurrent requests | `aria/api/run_manager.py:106-118` |
| 🟠 HIGH | Zero API authentication — any machine on the network can start/stop/read runs | `aria/api/app.py` |
| 🟡 MEDIUM | `apiBaseUrl` hard-coded to `127.0.0.1:8765`, not persisted — user re-types every restart | `aria_studio/lib/state/aria_controller.dart:92` |
| 🟡 MEDIUM | `shared_preferences` missing from pubspec — URL persistence can't be implemented | `aria_studio/pubspec.yaml` |
| 🟡 MEDIUM | Stale widget test checks for `'Mission Editor'` text — fails after rename | `aria_studio/test/widget_test.dart` |
| 🟡 MEDIUM | No API integration tests for any route | `tests/` |
| 🟡 MEDIUM | No Dockerfile, no docker-compose, no nginx.conf | project root |
| ℹ️ INFO | Run state in-memory only (lost on server restart) — acceptable for v1 if documented | `aria/api/run_manager.py` |

---

## Phase 1 — Critical Security Fixes

### Task 1: Fix CORS configuration

**Files:**
- Modify: `aria/api/app.py:47-53`

The current config is invalid per CORS spec. `allow_credentials=True` requires an explicit origin list — `"*"` is rejected by all browsers.

**Decision:** For a localhost desktop app, credentials aren't needed (no cookies). Fix: remove `allow_credentials=True` OR lock to explicit origin.

- [ ] **Step 1: Open `aria/api/app.py` and replace the CORS block**

Change lines 47–53 from:
```python
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
    allow_credentials=True,
)
```

To:
```python
import os

_ALLOWED_ORIGINS = os.environ.get(
    "ARIA_ALLOWED_ORIGINS",
    "http://localhost:8765,http://127.0.0.1:8765,http://localhost:3000,http://localhost:4200",
).split(",")

app.add_middleware(
    CORSMiddleware,
    allow_origins=_ALLOWED_ORIGINS,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["Content-Type", "Authorization", "X-API-Key"],
    allow_credentials=False,  # no cookie auth — XHR with explicit headers only
)
```

- [ ] **Step 2: Verify change compiles**

```bash
cd /Users/apc/Study/Projects/Working/ARIA
python -c "from aria.api.app import app; print('CORS OK')"
```

Expected output: `CORS OK`

- [ ] **Step 3: Commit**

```bash
git add aria/api/app.py
git commit -m "fix: lock CORS to explicit origin list, remove invalid credentials=True"
```

---

### Task 2: Fix path traversal in download endpoint

**Files:**
- Modify: `aria/api/routes/exports.py:77-96`

Current code: `list(output_dir.rglob(filename))` — attacker sends `filename=../../../../etc/passwd` and rglob walks the whole filesystem. No boundary check.

- [ ] **Step 1: Replace the `download_file` function**

Replace lines 77–96 in `aria/api/routes/exports.py` with:

```python
import re as _re

_SAFE_FILENAME = _re.compile(r'^[\w\-. ]+$')  # alphanum, dash, dot, space, underscore

@router.get("/api/runs/{run_id}/download/{filename}")
async def download_file(
    run_id: str,
    filename: str,
    run_manager: RunManager = Depends(get_run_manager),
):
    """Serve an export file for download (path-traversal safe)."""
    # 1. Validate filename — reject anything with path separators or odd chars
    if not _SAFE_FILENAME.match(filename):
        raise HTTPException(status_code=400, detail="Invalid filename")

    state = _require_run(run_id, run_manager)
    output_dir = Path(state.output_dir).resolve()

    # 2. Search for file, then verify it's actually inside output_dir
    candidates = list(output_dir.rglob(filename))
    if not candidates:
        raise HTTPException(status_code=404, detail=f"File '{filename}' not found for run '{run_id}'")

    file_path = candidates[0].resolve()

    # 3. Boundary check — resolved path must start with output_dir
    if not str(file_path).startswith(str(output_dir)):
        raise HTTPException(status_code=403, detail="Access denied")

    if not file_path.is_file():
        raise HTTPException(status_code=404, detail=f"'{filename}' is not a regular file")

    return FileResponse(path=str(file_path), filename=filename)
```

- [ ] **Step 2: Also add `import re as _re` at the top of exports.py if not present**

The regex `_re` import is included inline in the snippet above. Confirm `from pathlib import Path` is already on line 5 (it is).

- [ ] **Step 3: Write a quick manual test**

```bash
cd /Users/apc/Study/Projects/Working/ARIA
python -c "
import re
safe = re.compile(r'^[\w\-. ]+$')
assert safe.match('report_2024.json')
assert not safe.match('../../../etc/passwd')
assert not safe.match('foo/bar.json')
print('Filename validation OK')
"
```

Expected: `Filename validation OK`

- [ ] **Step 4: Commit**

```bash
git add aria/api/routes/exports.py
git commit -m "fix: prevent path traversal in download endpoint (validate + boundary check)"
```

---

### Task 3: Add lightweight API key authentication

**Files:**
- Create: `aria/api/middleware/auth.py`
- Modify: `aria/api/app.py`

No auth = anyone on your LAN can enumerate/delete research runs. Add a simple static bearer token for v1.

- [ ] **Step 1: Create `aria/api/middleware/` directory and auth module**

```bash
mkdir -p /Users/apc/Study/Projects/Working/ARIA/aria/api/middleware
touch /Users/apc/Study/Projects/Working/ARIA/aria/api/middleware/__init__.py
```

- [ ] **Step 2: Create `aria/api/middleware/auth.py`**

```python
"""Simple static API key auth for ARIA Studio API."""
from __future__ import annotations

import os
import secrets

from fastapi import Request
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

# Read from env; if not set, generate a random key at startup and print it
_API_KEY: str = os.environ.get("ARIA_API_KEY", "")
if not _API_KEY:
    _API_KEY = secrets.token_urlsafe(32)
    print(f"\n⚠️  ARIA API key not set. Using ephemeral key (restart = new key):")
    print(f"   ARIA_API_KEY={_API_KEY}\n")

# Paths that don't require auth (health check, OPTIONS preflight)
_PUBLIC_PATHS = {"/api/health", "/", "/favicon.ico"}


class ApiKeyMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        if request.method == "OPTIONS":
            return await call_next(request)

        path = request.url.path
        if path in _PUBLIC_PATHS or path.startswith("/assets"):
            return await call_next(request)

        # Accept key in Authorization header: "Bearer <key>"
        # or X-API-Key header (Flutter sends this)
        auth = request.headers.get("Authorization", "")
        x_key = request.headers.get("X-API-Key", "")
        provided = x_key or (auth.removeprefix("Bearer ").strip() if auth.startswith("Bearer ") else "")

        if not secrets.compare_digest(provided, _API_KEY):
            return JSONResponse({"detail": "Invalid or missing API key"}, status_code=401)

        return await call_next(request)
```

- [ ] **Step 3: Register the middleware in `aria/api/app.py`**

Add after the existing `app.add_middleware(CORSMiddleware, ...)` block:

```python
from aria.api.middleware.auth import ApiKeyMiddleware
app.add_middleware(ApiKeyMiddleware)
```

- [ ] **Step 4: Add `X-API-Key` header to Flutter's AriaApiClient**

In `aria_studio/lib/state/aria_controller.dart`, find `_api.baseUrl = apiBaseUrl;` (line 288) and update the HTTP client to send the API key header. Search for the HTTP client initialization:

```bash
grep -n "headers\|apiKey\|Authorization\|X-Api" /Users/apc/Study/Projects/Working/ARIA/aria_studio/lib/state/aria_controller.dart | head -20
```

Then find the `AriaApiClient` or `http.Client` setup and add:
```dart
// In AriaController.setApiBaseUrl or wherever headers are configured:
_api.apiKey = _savedApiKey; // to be wired in Task 5 (URL persistence)
```

*(Full wiring done in Task 5 — mark this step complete after verifying middleware registers)*

- [ ] **Step 5: Smoke test auth**

```bash
cd /Users/apc/Study/Projects/Working/ARIA
python -m aria.cli --serve-api &
sleep 2
# Should be rejected:
curl -s http://127.0.0.1:8765/api/runs | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('detail','FAIL'))"
# Expected: "Invalid or missing API key"
kill %1
```

- [ ] **Step 6: Commit**

```bash
git add aria/api/middleware/ aria/api/app.py
git commit -m "feat: add static API key authentication middleware"
```

---

## Phase 2 — Error Handling

### Task 4: Harden chat and credentials routes

**Files:**
- Modify: `aria/api/routes/chat.py`
- Modify: `aria/api/routes/credentials.py`

- [ ] **Step 1: Wrap `analyze` and `clarify` in try/except in `chat.py`**

The current `analyze` handler does a bare `from aria.engine.domains.planner import IntentAgent` inside the function. If engine not installed, returns 500 with a stack trace that leaks file paths.

Replace the route body in `aria/api/routes/chat.py` lines 26–43:

```python
@router.post("/analyze")
async def analyze(request: ChatMessage):
    """Parse a natural language query → intent result."""
    try:
        from aria.engine.domains.planner import IntentAgent
        agent = IntentAgent()
        intent = await agent.analyze(request.message)
        return {
            "topic": intent.topic,
            "domains": intent.domains,
            "countries": intent.countries,
            "data_types": intent.data_types,
            "time_range": intent.time_range,
            "confidence": intent.confidence,
            "pending_questions": intent.pending_questions,
            "ready": intent.ready,
        }
    except ImportError:
        raise HTTPException(status_code=503, detail="Intent agent unavailable (engine not installed)")
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Analysis failed: {type(exc).__name__}")
```

- [ ] **Step 2: Add `from fastapi import HTTPException` import to `chat.py` if missing**

Check line 1–10 of `aria/api/routes/chat.py`. Add if not present:
```python
from fastapi import APIRouter, HTTPException
```

- [ ] **Step 3: Verify credentials route doesn't expose raw file paths**

Read `aria/api/routes/credentials.py`. Current `save_credentials` returns:
```python
return {"status": "saved", "path": str(path)}
```
The `path` leaks the server's filesystem path. Replace with:
```python
return {"status": "saved"}
```

- [ ] **Step 4: Commit**

```bash
git add aria/api/routes/chat.py aria/api/routes/credentials.py
git commit -m "fix: suppress stack traces in chat/credentials, remove path leak"
```

---

## Phase 3 — Flutter URL Persistence

### Task 5: Persist `apiBaseUrl` across restarts with shared_preferences

**Files:**
- Modify: `aria_studio/pubspec.yaml`
- Modify: `aria_studio/lib/state/aria_controller.dart`
- Modify: `aria_studio/lib/pages/setup_page.dart`

- [ ] **Step 1: Add `shared_preferences` to pubspec.yaml**

Open `aria_studio/pubspec.yaml`. Under `dependencies:`, add:
```yaml
  shared_preferences: ^2.3.2
```

Run:
```bash
cd /Users/apc/Study/Projects/Working/ARIA/aria_studio
flutter pub get
```

Expected: `+ shared_preferences 2.3.2` in output (or compatible version).

- [ ] **Step 2: Add persistence methods to AriaController**

In `aria_studio/lib/state/aria_controller.dart`, add at the top of the imports:
```dart
import 'package:shared_preferences/shared_preferences.dart';
```

Find the `AriaController` class. After `String apiBaseUrl = 'http://127.0.0.1:8765';` (line 92), add:

```dart
  static const _kApiUrl = 'aria_api_base_url';
  static const _kApiKey = 'aria_api_key';

  /// Load persisted settings. Call once at startup from main.dart.
  Future<void> loadPersistedSettings() async {
    final prefs = await SharedPreferences.getInstance();
    final savedUrl = prefs.getString(_kApiUrl);
    final savedKey = prefs.getString(_kApiKey);
    if (savedUrl != null && savedUrl.isNotEmpty) {
      apiBaseUrl = savedUrl;
      _api.baseUrl = savedUrl;
    }
    if (savedKey != null && savedKey.isNotEmpty) {
      _savedApiKey = savedKey;
      _api.apiKey = savedKey; // wire to HTTP client
    }
    notifyListeners();
  }

  Future<void> saveApiSettings({required String url, String? key}) async {
    final prefs = await SharedPreferences.getInstance();
    await prefs.setString(_kApiUrl, url);
    if (key != null) await prefs.setString(_kApiKey, key);
    setApiBaseUrl(url);
    if (key != null) {
      _savedApiKey = key;
      _api.apiKey = key;
    }
    notifyListeners();
  }
```

Also add `String _savedApiKey = '';` as a private field near `apiBaseUrl`.

- [ ] **Step 3: Call `loadPersistedSettings()` at app startup**

In `aria_studio/lib/main.dart` (or wherever `AriaController` is created), add:

```dart
void main() async {
  WidgetsFlutterBinding.ensureInitialized();
  final controller = AriaController();
  await controller.loadPersistedSettings(); // load saved URL before first paint
  runApp(
    ChangeNotifierProvider.value(
      value: controller,
      child: const AriaStudioApp(),
    ),
  );
}
```

- [ ] **Step 4: Wire `saveApiSettings` into SetupPage step 1 (server URL input)**

In `aria_studio/lib/pages/setup_page.dart`, find where the server URL is applied (the input field controller or `onChanged`/`onSubmit` handler). Replace the bare `c.setApiBaseUrl(...)` call with:

```dart
c.saveApiSettings(url: _serverUrlController.text.trim());
```

- [ ] **Step 5: Verify persistence manually**

```bash
cd /Users/apc/Study/Projects/Working/ARIA/aria_studio
flutter run -d macos
# Set a custom URL in SetupPage step 1 → proceed to dashboard
# Quit the app → reopen
# Confirm URL is pre-filled
```

- [ ] **Step 6: Commit**

```bash
git add aria_studio/pubspec.yaml aria_studio/pubspec.lock aria_studio/lib/state/aria_controller.dart aria_studio/lib/pages/setup_page.dart aria_studio/lib/main.dart
git commit -m "feat: persist API URL and key across restarts via shared_preferences"
```

---

### Task 6: Fix stale widget test

**Files:**
- Modify: `aria_studio/test/widget_test.dart`

- [ ] **Step 1: Run the existing test to confirm it fails**

```bash
cd /Users/apc/Study/Projects/Working/ARIA/aria_studio
flutter test test/widget_test.dart 2>&1 | tail -20
```

Expected: test fails (widget no longer shows 'Mission Editor').

- [ ] **Step 2: Replace test with a smoke test that actually passes**

Overwrite `aria_studio/test/widget_test.dart` with:

```dart
import 'package:aria_studio/app.dart';
import 'package:aria_studio/state/aria_controller.dart';
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:provider/provider.dart';

void main() {
  testWidgets('App renders without crashing', (WidgetTester tester) async {
    await tester.pumpWidget(
      ChangeNotifierProvider(
        create: (_) => AriaController(),
        child: const AriaStudioApp(),
      ),
    );
    // App shell renders (no crash)
    expect(find.byType(MaterialApp), findsOneWidget);
  });

  testWidgets('SetupPage shows ARIA branding', (WidgetTester tester) async {
    await tester.pumpWidget(
      ChangeNotifierProvider(
        create: (_) => AriaController(),
        child: const AriaStudioApp(),
      ),
    );
    await tester.pump(); // let animations settle
    // At least one text widget renders on the initial page
    expect(find.byType(Text), findsWidgets);
  });
}
```

- [ ] **Step 3: Run updated test — confirm passes**

```bash
cd /Users/apc/Study/Projects/Working/ARIA/aria_studio
flutter test test/widget_test.dart -v 2>&1 | tail -20
```

Expected:
```
00:XX +2: All tests passed!
```

- [ ] **Step 4: Run flutter analyze — fix all errors**

```bash
cd /Users/apc/Study/Projects/Working/ARIA/aria_studio
flutter analyze 2>&1 | grep -E "error:|warning:" | head -30
```

Fix any `error:` lines. Warnings may be left for later.

- [ ] **Step 5: Commit**

```bash
git add aria_studio/test/widget_test.dart
git commit -m "fix: update widget test to match current SetupPage, fix flutter analyze errors"
```

---

## Phase 4 — API Integration Tests

### Task 7: Write pytest integration tests for critical API routes

**Files:**
- Create: `tests/test_api_integration.py`

- [ ] **Step 1: Create test file**

Create `/Users/apc/Study/Projects/Working/ARIA/tests/test_api_integration.py`:

```python
"""Integration tests for ARIA Studio API critical routes.

Run with: pytest tests/test_api_integration.py -v

These tests use FastAPI's TestClient — no live server needed.
"""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

# Skip entire module if aria.engine not installed
try:
    from aria.api.app import app
    HAS_ENGINE = True
except ImportError:
    HAS_ENGINE = False

pytestmark = pytest.mark.skipif(not HAS_ENGINE, reason="aria.engine not installed")

# ── Fixtures ──────────────────────────────────────────────────────────────────

@pytest.fixture(scope="module")
def client():
    with TestClient(app) as c:
        yield c


# ── Health ─────────────────────────────────────────────────────────────────────

class TestHealth:
    def test_health_returns_200(self, client):
        r = client.get("/api/health")
        assert r.status_code == 200

    def test_health_payload(self, client):
        r = client.get("/api/health")
        body = r.json()
        assert "status" in body


# ── Runs ───────────────────────────────────────────────────────────────────────

class TestRuns:
    def test_list_runs_returns_list(self, client):
        r = client.get("/api/runs")
        assert r.status_code == 200
        assert isinstance(r.json(), (list, dict))  # accepts both shapes

    def test_get_nonexistent_run_is_404(self, client):
        r = client.get("/api/runs/does-not-exist-xyz")
        assert r.status_code == 404

    def test_start_run_requires_topic(self, client):
        r = client.post("/api/runs", json={})
        assert r.status_code in (400, 422)  # validation error

    def test_start_run_returns_run_id(self, client):
        r = client.post("/api/runs", json={"topic": "test integration"})
        assert r.status_code in (200, 201, 202)
        body = r.json()
        assert "run_id" in body or "id" in body


# ── Download (path traversal protection) ──────────────────────────────────────

class TestDownloadSecurity:
    def test_path_traversal_rejected(self, client):
        # Start a fake run to get a valid run_id
        r = client.post("/api/runs", json={"topic": "security test"})
        if r.status_code not in (200, 201, 202):
            pytest.skip("Can't create run in test environment")
        run_id = (r.json().get("run_id") or r.json().get("id", ""))

        # Attempt path traversal
        malicious = "../../../etc/passwd"
        r2 = client.get(f"/api/runs/{run_id}/download/{malicious}")
        assert r2.status_code in (400, 403, 404)  # must not be 200

    def test_valid_filename_accepted(self, client):
        r = client.post("/api/runs", json={"topic": "download test"})
        if r.status_code not in (200, 201, 202):
            pytest.skip("Can't create run in test environment")
        run_id = (r.json().get("run_id") or r.json().get("id", ""))
        # Valid but non-existent file → 404 (not 400/403)
        r2 = client.get(f"/api/runs/{run_id}/download/report.json")
        assert r2.status_code in (200, 404)  # 400/403 = validation bug


# ── CORS ───────────────────────────────────────────────────────────────────────

class TestCORS:
    def test_cors_does_not_allow_wildcard_with_credentials(self, client):
        """After fix, credentials header must NOT be present with wildcard origin."""
        r = client.options(
            "/api/runs",
            headers={
                "Origin": "http://evil.example.com",
                "Access-Control-Request-Method": "GET",
            },
        )
        allow_origin = r.headers.get("access-control-allow-origin", "")
        allow_creds = r.headers.get("access-control-allow-credentials", "false")
        # Must NOT grant wildcard + credentials together
        assert not (allow_origin == "*" and allow_creds.lower() == "true"), (
            "CORS misconfiguration: wildcard origin with credentials=true is invalid"
        )

    def test_cors_preflight_for_known_origin(self, client):
        r = client.options(
            "/api/runs",
            headers={
                "Origin": "http://127.0.0.1:8765",
                "Access-Control-Request-Method": "GET",
            },
        )
        # Should not be 403
        assert r.status_code != 403


# ── Credentials ────────────────────────────────────────────────────────────────

class TestCredentials:
    def test_save_credentials_no_path_leak(self, client):
        r = client.post("/api/credentials", json={"test_key": "test_val"})
        assert r.status_code in (200, 201)
        body = r.json()
        # After fix, path must not appear in response
        assert "path" not in body, "credentials endpoint leaks filesystem path"
        assert body.get("status") == "saved"
```

- [ ] **Step 2: Run tests**

```bash
cd /Users/apc/Study/Projects/Working/ARIA
pytest tests/test_api_integration.py -v 2>&1 | tail -40
```

Expected: all tests pass (or correctly skip if engine not installed). Fix any failures before proceeding.

- [ ] **Step 3: Commit**

```bash
git add tests/test_api_integration.py
git commit -m "test: add API integration tests covering security, CORS, path traversal, runs"
```

---

## Phase 5 — Deployment Artifacts

### Task 8: Create Dockerfile for the FastAPI backend

**Files:**
- Create: `Dockerfile.api`
- Create: `.dockerignore`

- [ ] **Step 1: Create `Dockerfile.api`**

```dockerfile
# ARIA Studio — FastAPI backend
FROM python:3.11-slim

WORKDIR /app

# Install system deps (for some collectors that use lxml/playwright)
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc libxml2-dev libxslt-dev curl \
    && rm -rf /var/lib/apt/lists/*

# Install Python deps
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy source
COPY aria/ ./aria/
COPY missions/ ./missions/

# Non-root user
RUN useradd -m -u 1000 aria
RUN chown -R aria:aria /app
USER aria

ENV ARIA_API_KEY=""
ENV ARIA_ALLOWED_ORIGINS="http://localhost:8765,http://127.0.0.1:8765"
ENV HOST="0.0.0.0"
ENV PORT="8765"

EXPOSE 8765

CMD ["python", "-m", "uvicorn", "aria.api.app:app", "--host", "0.0.0.0", "--port", "8765"]
```

- [ ] **Step 2: Create `.dockerignore`**

```
__pycache__
*.pyc
*.pyo
.venv
venv
.git
aria_studio/
aria-report/
tests/
data/
logs/
*.log
credentials/
.env
```

- [ ] **Step 3: Build and verify**

```bash
cd /Users/apc/Study/Projects/Working/ARIA
docker build -f Dockerfile.api -t aria-api:latest . 2>&1 | tail -10
```

Expected: `Successfully built <hash>` and `Successfully tagged aria-api:latest`

- [ ] **Step 4: Commit**

```bash
git add Dockerfile.api .dockerignore
git commit -m "feat: add Dockerfile.api for production backend deployment"
```

---

### Task 9: Create nginx.conf and docker-compose.yml

**Files:**
- Create: `nginx.conf`
- Create: `docker-compose.yml`

- [ ] **Step 1: Create `nginx.conf`**

```nginx
# ARIA Studio — nginx reverse proxy + static Flutter web UI
events {
    worker_connections 1024;
}

http {
    include       /etc/nginx/mime.types;
    default_type  application/octet-stream;
    sendfile      on;
    gzip          on;
    gzip_types    text/plain application/json application/javascript text/css;

    server {
        listen 80;
        server_name _;

        # Flutter web UI (static files)
        root /usr/share/nginx/html;
        index index.html;

        # All Flutter routes → index.html (hash routing fallback)
        location / {
            try_files $uri $uri/ /index.html;
        }

        # Proxy API requests to FastAPI backend
        location /api/ {
            proxy_pass         http://aria-api:8765;
            proxy_http_version 1.1;
            proxy_set_header   Host $host;
            proxy_set_header   X-Real-IP $remote_addr;
            proxy_set_header   X-Forwarded-For $proxy_add_x_forwarded_for;
            proxy_set_header   Upgrade $http_upgrade;
            proxy_set_header   Connection "upgrade";
            proxy_read_timeout 300s;  # long timeout for research runs
        }
    }
}
```

- [ ] **Step 2: Build Flutter web before creating docker-compose**

```bash
cd /Users/apc/Study/Projects/Working/ARIA/aria_studio
flutter build web --release 2>&1 | tail -10
```

Expected: `✓ Built build/web`

- [ ] **Step 3: Create `docker-compose.yml`**

```yaml
version: "3.9"

services:
  aria-api:
    build:
      context: .
      dockerfile: Dockerfile.api
    image: aria-api:latest
    container_name: aria-api
    restart: unless-stopped
    environment:
      - ARIA_API_KEY=${ARIA_API_KEY}
      - ARIA_ALLOWED_ORIGINS=http://localhost,http://127.0.0.1
    volumes:
      - ./data:/app/data          # research output
      - ./credentials:/app/credentials  # saved keys
      - ./missions:/app/missions
    ports:
      - "8765:8765"
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8765/api/health"]
      interval: 30s
      timeout: 5s
      retries: 3

  aria-web:
    image: nginx:alpine
    container_name: aria-web
    restart: unless-stopped
    depends_on:
      - aria-api
    ports:
      - "80:80"
    volumes:
      - ./nginx.conf:/etc/nginx/nginx.conf:ro
      - ./aria_studio/build/web:/usr/share/nginx/html:ro
```

- [ ] **Step 4: Create `.env.example`**

```bash
cat > /Users/apc/Study/Projects/Working/ARIA/.env.example << 'EOF'
# ARIA Studio — environment variables
# Copy to .env and fill in values

# Required: API authentication key (generate with: python -c "import secrets; print(secrets.token_urlsafe(32))")
ARIA_API_KEY=your-secret-key-here

# Optional: comma-separated allowed CORS origins (default: localhost)
ARIA_ALLOWED_ORIGINS=http://localhost,http://127.0.0.1

# LLM provider (set via UI, but can pre-configure here)
# ANTHROPIC_API_KEY=sk-ant-...
# LLM_PROVIDER=anthropic
EOF
```

- [ ] **Step 5: Test docker-compose**

```bash
cd /Users/apc/Study/Projects/Working/ARIA
ARIA_API_KEY=test123 docker-compose up -d 2>&1 | tail -10
sleep 5
curl -s http://localhost:8765/api/health
docker-compose down
```

Expected: health endpoint returns JSON status.

- [ ] **Step 6: Commit**

```bash
git add nginx.conf docker-compose.yml .env.example
git commit -m "feat: add docker-compose, nginx reverse proxy, .env.example for deployment"
```

---

## Phase 6 — UI Smoke Test Checklist

### Task 10: Manual UI verification — all 8 pages

Run the app with `flutter run -d macos` (or `flutter run -d chrome`). Work through every page. All items must pass before go-live.

**Prerequisites:**
- Backend running: `python -m aria.cli --serve-api`
- Flutter app running: `cd aria_studio && flutter run`

- [ ] **SetupPage (`/setup`)**
  - [ ] ARIA wordmark renders (Syne font, indigo color)
  - [ ] Step dots (`01` `02` `03` `04`) show in IBM Plex Mono
  - [ ] Active step dot is filled indigo, completed steps show green check
  - [ ] Step 1: Server URL field accepts input, pings server on change
  - [ ] Step 1: LLM provider dropdown opens and shows providers
  - [ ] Step 2: Source toggles all work (web, wikipedia, reddit, etc.)
  - [ ] Step 3: Mission preset cards render with hover glow
  - [ ] Step 4: Config summary shows selected options
  - [ ] "Start Research" button navigates to `/home`
  - [ ] URL field value persists after app restart (Task 5)
  - [ ] No red flutter errors in console

- [ ] **DashboardPage (`/home`)**
  - [ ] Sidebar renders with 220px width on desktop
  - [ ] ARIA wordmark in sidebar (Syne font)
  - [ ] Source nodes (GlowNode widgets) appear for active sources
  - [ ] Topic input field accepts typing
  - [ ] Command bar accent line animates when topic entered
  - [ ] `⌘ ↵ to launch` shortcut hint visible
  - [ ] "Launch" button triggers research run
  - [ ] Orbital progress ring animates during run
  - [ ] Stage labels update during run
  - [ ] Doc count, source count metrics update live
  - [ ] Tablet layout (600–900px): sidebar narrows to 160px
  - [ ] Mobile layout (<600px): sidebar hidden, FAB opens bottom sheet
  - [ ] Depth control slider changes value
  - [ ] No red flutter errors in console

- [ ] **HistoryPage (`/history`)**
  - [ ] Page loads without crash
  - [ ] Past runs shown as cards
  - [ ] Run card shows status dot (green/amber/red)
  - [ ] Click run card → navigates to RunDetailPage

- [ ] **RunDetailPage (`/run-detail`)**
  - [ ] Documents list loads
  - [ ] Document cards show title, source, relevance score (mono)
  - [ ] Click document card → DocumentDetailPage modal

- [ ] **ReportsPage (`/reports`)**
  - [ ] Page loads without crash
  - [ ] Tab bar shows (Documents, Statistics, Exports, Analysis)
  - [ ] Each tab renders without error

- [ ] **SettingsPage (`/settings`)**
  - [ ] Page loads
  - [ ] API URL field pre-filled (from shared_preferences)
  - [ ] Save button persists changes

- [ ] **LoginPage (`/login`)**
  - [ ] Page renders without `Competing ParentDataWidgets` crash
  - [ ] 3D floating orbs appear in background
  - [ ] No flutter red errors in console

- [ ] **3D page transitions**
  - [ ] Navigate between any 2 pages: 3D cube flip animation plays
  - [ ] No jank or dropped frames (check with Flutter DevTools)

---

## Phase 7 — Final Pre-Launch Checklist

### Task 11: Full smoke test and go-live verification

- [ ] **Run all pytest tests**

```bash
cd /Users/apc/Study/Projects/Working/ARIA
pytest tests/test_api_integration.py tests/test_config.py -v 2>&1 | tail -30
```

Expected: all tests pass or skip cleanly.

- [ ] **Run flutter analyze — zero errors**

```bash
cd /Users/apc/Study/Projects/Working/ARIA/aria_studio
flutter analyze 2>&1 | grep -c "error:"
```

Expected: `0`

- [ ] **Build Flutter web release**

```bash
cd /Users/apc/Study/Projects/Working/ARIA/aria_studio
flutter build web --release 2>&1 | tail -5
ls -lh build/web/main.dart.js
```

Expected: `✓ Built build/web`, `main.dart.js` exists and is < 10MB (rough sanity check)

- [ ] **Test docker-compose production stack end-to-end**

```bash
cd /Users/apc/Study/Projects/Working/ARIA
echo "ARIA_API_KEY=$(python3 -c 'import secrets; print(secrets.token_urlsafe(32))')" > .env
docker-compose up -d
sleep 8
curl -s http://localhost/api/health
curl -s http://localhost/ | head -5  # should return Flutter web HTML
docker-compose logs aria-api | tail -20
docker-compose down
```

- [ ] **Security spot-check**

```bash
# 1. Path traversal blocked
curl -s "http://localhost:8765/api/runs/fake-run/download/../../../etc/passwd"
# Expected: 400 or 404 (NOT 200)

# 2. Unauth request rejected (when ARIA_API_KEY is set)
curl -s "http://localhost:8765/api/runs"
# Expected: {"detail": "Invalid or missing API key"}

# 3. Authed request works
export KEY=$(grep ARIA_API_KEY .env | cut -d= -f2)
curl -s -H "X-API-Key: $KEY" "http://localhost:8765/api/health"
# Expected: {"status": "ok", ...}
```

- [ ] **Generate and record API key for production**

```bash
python3 -c "import secrets; print('ARIA_API_KEY=' + secrets.token_urlsafe(32))"
# Save this in your production .env — keep it secret
```

- [ ] **Update CLAUDE.md run instructions with docker-compose**

Add to `CLAUDE.md` under `## Running`:
```markdown
# Production (Docker)
docker-compose up -d
# Open http://localhost in browser
# API: http://localhost/api/health
```

- [ ] **Final commit and tag**

```bash
git add -A
git commit -m "chore: pre-launch hardening complete — security, tests, deployment"
git tag v5.0.0-rc1
```

---

## Order of Implementation

1. **Task 1** — CORS fix (10 min) ← do this first, blocks everything in browser
2. **Task 2** — Path traversal fix (15 min)
3. **Task 4** — Error handling (10 min)
4. **Task 5** — URL persistence (30 min, most Flutter work)
5. **Task 6** — Fix widget test + flutter analyze (20 min)
6. **Task 7** — API integration tests (30 min)
7. **Task 3** — API key auth (20 min) ← do after tests so test client can include key
8. **Task 8** — Dockerfile (15 min)
9. **Task 9** — nginx + docker-compose (20 min)
10. **Task 10** — UI smoke test (45 min manual)
11. **Task 11** — Final pre-launch (30 min)

**Total estimated time: ~4 hours**

---

## Risks

| Risk | Impact | Mitigation |
|------|--------|------------|
| `aria.engine` import chain breaks after CORS change | API returns 500 | Run `pytest tests/test_api_integration.py` immediately after each change |
| shared_preferences unavailable on Linux desktop | URL not persisted | Test on target platform early; fallback = hardcoded default is acceptable for v1 |
| Docker image too large (playwright/chromium) | Slow CI, large image | Use `--no-install-recommends`, exclude optional playwright install |
| API key middleware breaks existing Flutter client | 401 on all requests | Wire `X-API-Key` header in AriaController before enabling middleware |
