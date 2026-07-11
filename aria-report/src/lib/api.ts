const BASE = "";

// ---------------------------------------------------------------------------
// API key store — fetched once on app mount, injected into every request
// ---------------------------------------------------------------------------
let _apiKey: string = "";
export function setApiKey(key: string): void {
  _apiKey = key;
}
export function getApiKey(): string {
  return _apiKey;
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${BASE}${path}`, {
    ...init,
    headers: {
      "Content-Type": "application/json",
      ...(_apiKey ? { "X-API-Key": _apiKey } : {}),
      ...init?.headers,
    },
  });
  if (!res.ok) {
    const text = await res.text().catch(() => res.statusText);
    throw new Error(`${res.status}: ${text}`);
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
        const text = await res.text().catch(() => res.statusText);
        throw new Error(`${res.status}: ${text}`);
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
      request<{ provider: string; model: string; base_url: string; configured: boolean }>(
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
};
