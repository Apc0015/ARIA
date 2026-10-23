import { useEffect, useState } from "react";
import { useQueryClient } from "@tanstack/react-query";

const REFRESH_THROTTLE_MS = 750;

/**
 * Subscribe to a run's live event stream (SSE) and refresh the run's
 * queries as events arrive. Polling in useRun stays as the fallback when
 * the stream is unavailable (e.g. a proxy that buffers responses).
 */
export function useRunStream(runId: string | undefined) {
  const queryClient = useQueryClient();
  const [connected, setConnected] = useState(false);

  useEffect(() => {
    if (!runId || typeof EventSource === "undefined") return;

    const source = new EventSource(`/api/runs/${encodeURIComponent(runId)}/stream`, {
      withCredentials: true,
    });
    let timer: ReturnType<typeof setTimeout> | null = null;

    const refresh = () => {
      if (timer) return;
      timer = setTimeout(() => {
        timer = null;
        queryClient.invalidateQueries({ queryKey: ["run", runId] });
        queryClient.invalidateQueries({ queryKey: ["run-docs", runId] });
      }, REFRESH_THROTTLE_MS);
    };

    source.onopen = () => setConnected(true);
    source.onerror = () => setConnected(false); // EventSource retries on its own
    // Named events (status, collect_done, …) don't reach onmessage, so listen
    // for the ones that change what Monitor shows.
    const events = ["status", "source_started", "source_done", "source_failed", "collect_done", "clean_progress", "clean_done"];
    events.forEach((name) => source.addEventListener(name, refresh));
    source.addEventListener("done", () => {
      refresh();
      setConnected(false);
      source.close();
    });

    return () => {
      if (timer) clearTimeout(timer);
      source.close();
      setConnected(false);
    };
  }, [runId, queryClient]);

  return { connected };
}
