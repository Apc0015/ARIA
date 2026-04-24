import { useQuery } from "@tanstack/react-query";
import { api } from "@/lib/api";

export function useRun(runId: string, poll = false) {
  return useQuery({
    queryKey: ["run", runId],
    queryFn: () => api.runs.get(runId),
    refetchInterval: poll ? 3_000 : false,
    enabled: Boolean(runId),
  });
}

export function useRunDocuments(runId: string, poll = false) {
  return useQuery({
    queryKey: ["run-docs", runId],
    queryFn: () => api.runs.documents(runId),
    refetchInterval: poll ? 3_000 : false,
    enabled: Boolean(runId),
  });
}
