import { useEffect, useRef, useState } from "react";

export interface StreamEvent {
  type: string;
  data: Record<string, unknown>;
  timestamp: number;
}

/**
 * Subscribe to a run's live SSE event stream.
 *
 * Returns the latest events list and a live documents array that
 * grows as cleaned documents arrive — no need to wait for pipeline end.
 *
 * Usage:
 *   const { events, liveDocuments, connected, done } = useRunStream(runId);
 */
export function useRunStream(runId: string | null) {
  const [events, setEvents] = useState<StreamEvent[]>([]);
  const [liveDocuments, setLiveDocuments] = useState<Record<string, unknown>[]>([]);
  const [connected, setConnected] = useState(false);
  const [done, setDone] = useState(false);
  const sourceRef = useRef<EventSource | null>(null);

  useEffect(() => {
    if (!runId) return;

    // Close any existing connection
    sourceRef.current?.close();
    setEvents([]);
    setLiveDocuments([]);
    setConnected(false);
    setDone(false);

    const apiKey = localStorage.getItem("aria_api_key") || "";
    const url = `/api/runs/${runId}/stream${apiKey ? `?token=${encodeURIComponent(apiKey)}` : ""}`;

    const source = new EventSource(url);
    sourceRef.current = source;

    source.onopen = () => setConnected(true);

    source.onerror = () => {
      setConnected(false);
      // EventSource auto-reconnects — don't close unless done
    };

    const handleEvent = (e: MessageEvent, eventType: string) => {
      try {
        const data = JSON.parse(e.data) as Record<string, unknown>;
        const event: StreamEvent = { type: eventType, data, timestamp: Date.now() };
        setEvents((prev) => [...prev.slice(-500), event]); // keep last 500

        // If the event carries a cleaned document, add it to liveDocuments
        if (data.document) {
          setLiveDocuments((prev) => [...prev, data.document as Record<string, unknown>]);
        }
      } catch {
        // ignore parse errors
      }
    };

    // Standard pipeline stages
    const stageNames = [
      "state", "query_plan", "collect", "source_done", "collect_done",
      "dedup", "clean", "clean_progress", "clean_done",
      "gap_detect", "knowledge_graph", "images",
      "export", "export_done", "report",
      "document", "progress", "event",
    ];

    stageNames.forEach((stage) => {
      source.addEventListener(stage, (e) => handleEvent(e as MessageEvent, stage));
    });

    source.addEventListener("done", (e) => {
      handleEvent(e as MessageEvent, "done");
      setDone(true);
      setConnected(false);
      source.close();
    });

    source.addEventListener("ping", () => {
      // keepalive — no action needed
    });

    return () => {
      source.close();
      sourceRef.current = null;
    };
  }, [runId]);

  const disconnect = () => {
    sourceRef.current?.close();
    setConnected(false);
  };

  return { events, liveDocuments, connected, done, disconnect };
}
