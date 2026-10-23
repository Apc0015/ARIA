const BASE = "";


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
  const res = await fetch(`${BASE}${path}`, {
    ...init,
    credentials: "include",
    headers: {
      "Content-Type": "application/json",
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
  Document,
} from "@/types";

export const api = {
  auth: {
    login: (email: string, password: string) => request<{ user: { email: string; role: string }; tenant_id: string }>("/api/auth/login", { method: "POST", body: JSON.stringify({ email, password }) }),
    logout: () => request<{ status: string }>("/api/auth/logout", { method: "POST" }),
    changePassword: (currentPassword: string, newPassword: string) => request<{ status: string }>("/api/auth/password", { method: "POST", body: JSON.stringify({ current_password: currentPassword, new_password: newPassword }) }),
    me: () => request<{ user: { email: string; role: string; tenant_id: string } }>("/api/auth/me"),
  },
  runs: {
    list: () => request<RunsListResponse>("/api/runs"),
    get: (runId: string) => request<Run>(`/api/runs/${runId}`),
    start: (payload: StartRunPayload) =>
      request<Run>("/api/runs", { method: "POST", body: JSON.stringify(payload) }),
    restart: (runId: string) => request<{ run_id: string; restarted_from: string; status: string }>(`/api/runs/${runId}/restart`, { method: "POST" }),
    documents: (runId: string) =>
      request<RunDocumentsResponse>(`/api/runs/${runId}/documents`),
    evidence: (runId: string, documentIndex: number) =>
      request<EvidenceResponse>(`/api/runs/${runId}/evidence/${documentIndex}`),
    intelligence: (runId: string) =>
      request<IntelligenceResponse>(`/api/runs/${runId}/intelligence`),
    findings: (runId: string) => request<{ run_id: string; findings: Finding[] }>(`/api/runs/${runId}/findings`),
    approveFinding: (runId: string, statement: string, evidenceDocumentIndexes: number[], notes = "") => request<{ run_id: string; finding: Finding }>(`/api/runs/${runId}/findings`, { method: "POST", body: JSON.stringify({ statement, evidence_document_indexes: evidenceDocumentIndexes, notes }) }),
  },
  exports: {
    markdown: (runId: string) => `${BASE}/api/runs/${runId}/export/markdown`,
    html: (runId: string) => `${BASE}/api/runs/${runId}/export/html`,
    zip: (runId: string) => `${BASE}/api/runs/${runId}/export/zip`,
    json: (runId: string) => `${BASE}/api/runs/${runId}/export/clean/json`,
    csv: (runId: string) => `${BASE}/api/runs/${runId}/export/clean/csv`,
    raw: (runId: string) => `${BASE}/api/runs/${runId}/export/raw`,
    findings: (runId: string) => `${BASE}/api/runs/${runId}/export/findings`,
    download: async (
      runId: string,
      kind: "markdown" | "html" | "zip" | "json" | "csv" | "raw" | "findings"
    ): Promise<{ blob: Blob; filename: string }> => {
      const path = {
        markdown: `/api/runs/${runId}/export/markdown`,
        html: `/api/runs/${runId}/export/html`,
        zip: `/api/runs/${runId}/export/zip`,
        json: `/api/runs/${runId}/export/clean/json`,
        csv: `/api/runs/${runId}/export/clean/csv`,
        raw: `/api/runs/${runId}/export/raw`,
        findings: `/api/runs/${runId}/export/findings`,
      }[kind];
      const info = await request<{ download_url?: string | null; filename?: string | null }>(path);
      if (!info.download_url) {
        throw new Error(`No ${kind} export is available for this run yet.`);
      }
      const res = await fetch(`${BASE}${info.download_url}`, {
        credentials: "include",
      });
      if (!res.ok) {
        throw new Error(await readError(res));
      }
      const filename = info.filename || `aria-${runId}-${kind}`;
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
  sourceSettings: {
    get: () => request<{ enabled_sources: Record<string, boolean> }>("/api/source-settings"),
    save: (enabledSources: Record<string, boolean>) => request<{ enabled_sources: Record<string, boolean> }>("/api/source-settings", { method: "PUT", body: JSON.stringify({ enabled_sources: enabledSources }) }),
  },
  organization: {
    users: () => request<{ users: OrganizationUser[] }>("/api/organization/users"),
    createUser: (email: string, password: string, role: OrganizationRole) =>
      request<{ user: OrganizationUser }>("/api/organization/users", {
        method: "POST",
        body: JSON.stringify({ email, password, role }),
      }),
    updateUser: (userId: string, updates: Partial<Pick<OrganizationUser, "role">> & { disabled?: boolean }) =>
      request<{ user: OrganizationUser }>(`/api/organization/users/${userId}`, {
        method: "PATCH",
        body: JSON.stringify(updates),
      }),
    resetUserPassword: (userId: string, newPassword: string) =>
      request<{ user: OrganizationUser }>(`/api/organization/users/${userId}/reset-password`, {
        method: "POST",
        body: JSON.stringify({ new_password: newPassword }),
      }),
    auditEvents: () => request<{ events: AuditEvent[] }>("/api/organization/audit-events"),
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

export interface EvidenceResponse {
  run_id: string;
  document_index: number;
  clean_document: Document;
  raw_document: Record<string, unknown>;
  raw_text: string;
  claims: unknown[];
  scoring_rationale: string;
  source_metadata: {
    source?: string;
    url?: string;
    published_at?: string;
    author?: string;
    collector_output?: Record<string, unknown>;
  };
}

export interface IntelligenceResponse {
  run_id: string;
  knowledge_graph: Record<string, unknown>;
  gap_analysis: { gaps?: unknown[]; follow_up_queries?: string[] };
  contradictions: unknown[];
  images: Array<Record<string, unknown>>;
}

export interface Finding {
  id: string;
  statement: string;
  evidence_document_indexes: number[];
  notes: string;
  approved_by: string;
  approved_at: string;
}

export type OrganizationRole = "admin" | "member" | "viewer";

export interface OrganizationUser {
  id: string;
  email: string;
  role: OrganizationRole;
  created_at: string;
  disabled_at: string | null;
}

export interface AuditEvent {
  id: string;
  user_id: string | null;
  event_type: string;
  metadata: Record<string, unknown>;
  created_at: string;
}
