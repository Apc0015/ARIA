const BASE = "";

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${BASE}${path}`, {
    headers: { "Content-Type": "application/json", ...init?.headers },
    ...init,
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
  },
  credentials: {
    get: () => request<CredentialsResponse>("/api/credentials"),
    save: (payload: Record<string, string>) =>
      request<{ status: string }>("/api/credentials", {
        method: "POST",
        body: JSON.stringify(payload),
      }),
  },
  health: {
    get: () => request<{ status: string }>("/api/health"),
  },
};
