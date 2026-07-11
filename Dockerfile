# =============================================================================
# ARIA — Multi-stage production Docker build
# Stage 1: Build the React frontend
# Stage 2: Build the Python backend + copy frontend dist
# =============================================================================

# ── Stage 1: Node / React build ───────────────────────────────────────────────
FROM node:20-alpine AS frontend-builder

WORKDIR /app/aria-report

# Install dependencies first (layer-cached until package.json changes)
COPY aria-report/package.json aria-report/package-lock.json* aria-report/pnpm-lock.yaml* ./
RUN npm install --frozen-lockfile 2>/dev/null || npm install

# Copy source and build
COPY aria-report/ .
RUN npm run build

# ── Stage 2: Python / FastAPI backend ────────────────────────────────────────
FROM python:3.11-slim AS backend

# System dependencies for Playwright, PyMuPDF, and OCR
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    curl \
    libglib2.0-0 \
    libnss3 \
    libnspr4 \
    libatk1.0-0 \
    libatk-bridge2.0-0 \
    libcups2 \
    libdrm2 \
    libdbus-1-3 \
    libxcb1 \
    libxkbcommon0 \
    libx11-6 \
    libxcomposite1 \
    libxdamage1 \
    libxext6 \
    libxfixes3 \
    libxrandr2 \
    libgbm1 \
    libpango-1.0-0 \
    libcairo2 \
    libasound2 \
    libpoppler-cpp-dev \
    tesseract-ocr \
    ffmpeg \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install Python dependencies (layer-cached until requirements.txt changes)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Install Playwright browser (Chromium only — smallest footprint)
RUN playwright install chromium --with-deps 2>/dev/null || true

# Copy application source
COPY aria/ ./aria/
COPY missions/ ./missions/

# Copy the built React app from Stage 1
COPY --from=frontend-builder /app/aria-report/dist ./aria-report/dist

# Create runtime directories
RUN mkdir -p data/runs data/raw data/clean data/exports credentials logs

# Non-root user for security
RUN useradd -m -u 1001 aria && chown -R aria:aria /app
USER aria

# Health check
HEALTHCHECK --interval=30s --timeout=5s --start-period=15s --retries=3 \
    CMD curl -f http://localhost:${ARIA_API_PORT:-8765}/api/health || exit 1

EXPOSE 8765

CMD ["python", "-m", "aria.cli", "--serve-api"]
