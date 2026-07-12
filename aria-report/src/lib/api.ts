const BASE = "";

// ---------------------------------------------------------------------------
// API key store — browser-provided, injected into every request when present.
// The backend must never disclose ARIA_API_KEY to clients.
// ---------------------------------------------------------------------------
const API_KEY_STORAGE = "aria.apiKey";

function loadStoredApiKey(): string {
  const envKey = import.meta.env.VITE_ARIA_API_KEY || "";
  if (envKey) return envKey;
  if (typeof window === "undefined") return "";
  if (typeof window.localStorage?.getItem !== "function") return "";
  try {
    return window.localStorage.getItem(API_KEY_STORAGE) || "";
  } catch {
    return "";
  }
}

let _apiKey: string = loadStoredApiKey();
let _apiKeyPromise: Promise<string> | null = null;
export function setApiKey(key: string): void {
  _apiKey = key;
  if (typeof window !== "undefined" && typeof window.localStorage?.setItem === "function") {
    try {
      if (key) window.localStorage.setItem(API_KEY_STORAGE, key);
      else window.localStorage.removeItem(API_KEY_STORAGE);
    } catch {
      // Ignore storage failures; the key still applies for this tab session.
    }
  }
}
export function getApiKey(): string {
  return _apiKey;
}

export async function ensureApiKey(): Promise<string> {
  if (_apiKey) return _apiKey;
  if (!_apiKeyPromise) _apiKeyPromise = Promise.resolve("");
  return _apiKeyPromise;
}

async function readError(res: Response): Promise<string> {
  const fallback = res.statusText || "Request failed";
  const text = await res.text().catch(() => "");
  if (!text) return `${res.status}: ${fallback}`;
  try {
    const parsed = JSON.parse(text) as { detail?: unknown; message?: unknown };
    const detail = parsed.detail ?? parsed.message;
    if (typeof detail === "string") return `${res.status}: ${detail}`;
    if (Array.isArray(detail)) return `${res.status}: ${detail.map(String).join(", ")}`;
    return `${res.status}: ${JSON.stringify(detail ?? parsed)}`;
  } catch {
    return `${res.status}: ${text}`;
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  if (path.startsWith("/api/") && !_apiKey) await ensureApiKey().catch(() => "");
  const res = await fetch(`${BASE}${path}`, {
    ...init,
    headers: {
      "Content-Type": "application/json",
      ...(_apiKey ? { "X-API-Key": _apiKey } : {}),
      ...init?.headers,
    },
  });
  if (!res.ok) {
    throw new Error(await readError(res));
  }
  return res.json() as Promise<T>;
}

import type {
  Run,
  RunsListResponse,
  RunDocumentsResponse,
  StartRunPayload,
  CredentialsResponse,
} from "@/types";

export const api = {
  runs: {
    list: () => request<RunsListResponse>("/api/runs"),
    get: (runId: string) => request<Run>(`/api/runs/${runId}`),
    start: (payload: StartRunPayload) =>
      request<Run>("/api/runs", { method: "POST", body: JSON.stringify(payload) }),
    documents: (runId: string) =>
      request<RunDocumentsResponse>(`/api/runs/${runId}/documents`),
  },
  exports: {
    markdown: (runId: string) => `${BASE}/api/runs/${runId}/export/markdown`,
    json: (runId: string) => `${BASE}/api/runs/${runId}/export/clean/json`,
    csv: (runId: string) => `${BASE}/api/runs/${runId}/export/clean/csv`,
    raw: (runId: string) => `${BASE}/api/runs/${runId}/export/raw`,
    download: async (
      runId: string,
      kind: "markdown" | "json" | "csv" | "raw"
    ): Promise<{ blob: Blob; filename: string }> => {
      const path = {
        markdown: `/api/runs/${runId}/export/markdown`,
        json: `/api/runs/${runId}/export/clean/json`,
        csv: `/api/runs/${runId}/export/clean/csv`,
        raw: `/api/runs/${runId}/export/raw`,
      }[kind];
      const info = await request<{ download_url?: string | null; path?: string | null }>(path);
      if (!info.download_url) {
        throw new Error(`No ${kind} export is available for this run yet.`);
      }
      const res = await fetch(`${BASE}${info.download_url}`, {
        headers: _apiKey ? { "X-API-Key": _apiKey } : undefined,
      });
      if (!res.ok) {
        throw new Error(await readError(res));
      }
      const filename = info.path?.split("/").pop() || `aria-${runId}-${kind}`;
      return { blob: await res.blob(), filename };
    },
  },
  credentials: {
    get: () => request<CredentialsResponse>("/api/credentials"),
    save: (payload: Record<string, string>) =>
      request<{ status: string }>("/api/credentials", {
        method: "POST",
        body: JSON.stringify(payload),
      }),
    verify: (sourceId: string, credentials: Record<string, string>) =>
      request<{ ok: boolean; message: string }>("/api/credentials/verify", {
        method: "POST",
        body: JSON.stringify({ source_id: sourceId, credentials }),
      }),
  },
  llm: {
    status: () =>
      request<{
        provider: string;
        model: string;
        base_url: string;
        configured: boolean;
        connected?: boolean | null;
        message?: string;
      }>(
        "/api/llm/status"
      ),
    models: (provider: string, baseUrl?: string) => {
      const qs = baseUrl ? `?provider=${provider}&base_url=${encodeURIComponent(baseUrl)}` : `?provider=${provider}`;
      return request<{ provider: string; models: string[]; connected: boolean }>(
        `/api/llm/models${qs}`
      );
    },
  },
  health: {
    get: () => request<{ status: string }>("/api/health"),
  },
  sources: {
    list: () =>
      request<{
        sources: Array<{ id: string; group: string; category?: string; name?: string }>;
        total?: number;
      }>("/api/sources"),
  },
};
