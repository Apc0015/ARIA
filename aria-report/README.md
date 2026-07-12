# ARIA React UI

React + Vite frontend for the ARIA FastAPI backend.

## Development

Start the backend from the repo root:

```bash
python3 -m aria.cli --serve-api
```

Start the React app:

```bash
cd aria-report
npm install
npm run dev
```

The Vite dev server proxies `/api/*` to `http://localhost:8765` by default. Override it when needed:

```bash
ARIA_API_PROXY_TARGET=http://localhost:8766 npm run dev -- --port 5174
```

## Production Build

```bash
cd aria-report
npm run build
```

The production files are written to `aria-report/dist`. Docker/nginx serves this directory and proxies `/api/*` to the `aria-api` service.
