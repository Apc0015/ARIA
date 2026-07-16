import { useNavigate } from "react-router-dom";
import { formatDistanceToNow } from "date-fns";
import { StatusDot } from "@/components/glass/StatusDot";
import { cn } from "@/lib/utils";
import type { Run } from "@/types";

const STATUS_LABEL: Record<string, string> = {
  running: "Running",
  pending: "Queued",
  queued: "Queued",
  completed: "Completed",
  failed: "Failed",
  cancelled: "Cancelled",
};

interface RunRowProps {
  run: Run;
  className?: string;
}

export function RunRow({ run, className }: RunRowProps) {
  const navigate = useNavigate();
  const isLive =
    run.status === "running" || run.status === "pending" || run.status === "queued";

  // Never show the run-id hash as the title. A real topic, or a plain label.
  const title = run.topic?.trim() || "Untitled run";
  const docs = run.total_documents;
  const when = run.updated_at
    ? formatDistanceToNow(new Date(run.updated_at), { addSuffix: true })
    : null;

  return (
    <button
      type="button"
      onClick={() =>
        navigate(isLive ? `/monitor/${run.run_id}` : `/report/${run.run_id}`)
      }
      className={cn(
        "group w-full text-left glass rounded-xl px-4 py-3 flex items-center gap-3.5",
        "transition-all duration-150 hover:shadow-elevation-elevated",
        "focus-visible:shadow-elevation-focus",
        className
      )}
    >
      <StatusDot status={run.status} />

      <div className="flex-1 min-w-0">
        <p className="text-[14px] font-medium text-aria-text1 truncate leading-tight">
          {title}
        </p>
        <p className="mt-0.5 flex items-center gap-1.5 text-[11px] text-aria-text4 truncate">
          <span>{STATUS_LABEL[run.status] ?? run.status}</span>
          <span aria-hidden>·</span>
          <span className="font-mono">{run.run_id}</span>
          {when && (
            <>
              <span aria-hidden>·</span>
              <span>{when}</span>
            </>
          )}
        </p>
      </div>

      <div className="flex-shrink-0 text-right">
        <p className="text-[15px] font-semibold text-aria-text1 tabular-nums leading-none">
          {docs != null ? docs.toLocaleString() : "—"}
        </p>
        <p className="mt-1 text-[10px] text-aria-text4">
          {docs === 1 ? "document" : "documents"}
        </p>
      </div>

      <svg
        className="flex-shrink-0 text-aria-text4 opacity-0 group-hover:opacity-100 transition-opacity"
        width="16" height="16" viewBox="0 0 16 16" fill="none" aria-hidden
      >
        <path d="M6 3.5L10.5 8L6 12.5" stroke="currentColor" strokeWidth="1.5"
          strokeLinecap="round" strokeLinejoin="round" />
      </svg>
    </button>
  );
}
