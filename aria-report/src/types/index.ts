export type RunStatus = "queued" | "pending" | "running" | "completed" | "failed" | "cancelled";

export interface Run {
  run_id: string;
  status: RunStatus;
  stage: string;
  message: string;
  created_at: string;
  updated_at: string;
  error?: string;
  topic?: string;
  documents?: Document[];
  sources_used?: string[];
  total_documents?: number;
  progress?: number; // 0–100
}

export interface Document {
  id?: string;
  title: string;
  url?: string;
  source: string;
  content?: string;
  summary?: string;
  relevance_score?: number;
  published_at?: string;
  is_relevant?: boolean;
}

export interface RunsListResponse {
  runs: Run[];
  total: number;
}

export interface RunDocumentsResponse {
  run_id: string;
  documents: Document[];
  total: number;
}

export interface StartRunPayload {
  topic?: string;
  intent?: string;
  depth_level?: 1 | 2 | 3 | 4 | 5;
  free_sources?: Record<string, boolean>;
  auth_sources?: Record<string, boolean>;
  cleaning?: {
    instructions?: string;
    output_schema?: Record<string, string>;
  };
  mission_yaml?: string;
  launch_mode?: "guided" | "manual" | "yaml";
  director_session_id?: string;
  ensemble_models?: string[];
  flags?: Record<string, unknown>;
}

export interface Credentials {
  [key: string]: string | undefined;
}

export interface CredentialsResponse {
  platforms?: Record<string, string | undefined>;
  [key: string]: string | Record<string, string | undefined> | undefined;
}
