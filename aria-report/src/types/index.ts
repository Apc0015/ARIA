export type RunStatus = "queued" | "pending" | "running" | "completed" | "completed_with_failures" | "collection_completed" | "interrupted" | "failed" | "cancelled";

export interface SourceRunStatus {
  source: string;
  status: "running" | "completed" | "failed";
  message?: string;
  documents?: number;
  started_at?: string;
  updated_at?: string;
  error?: string;
}

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
  source_status?: SourceRunStatus[];
  failures?: Array<{ scope?: string; message?: string; error?: string; source?: string }>;
  workflow?: "full_research" | "collection_only";
  available_exports?: string[];
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

export interface SeedPreview {
  title: string;
  authors: string[];
  year: string;
  journal: string;
  doi: string;
  url: string;
  abstract: string;
  ref_count: number | null;
  access_status: string;
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
  seed_doi?: string;
  seed_url?: string;
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
