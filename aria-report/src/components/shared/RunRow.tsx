import { useNavigate } from "react-router-dom";
import { formatDistanceToNow } from "date-fns";
import { StatusDot } from "@/components/glass/StatusDot";
import { cn } from "@/lib/utils";
import type { Run } from "@/types";

const statusBarColor: Record<string, string> = {
  running: "bg-aria-accent status-glow-violet",
  completed: "bg-aria-success",
  pending: "bg-aria-text4/30",
  failed: "bg-red-500",
  cancelled: "bg-aria-text4/30",
};

interface RunRowProps {
  run: Run;
  className?: string;
}

export function RunRow({ run, className }: RunRowProps) {
  const navigate = useNavigate();
  const bar = statusBarColor[run.status] ?? statusBarColor.pending;
  const isLive = run.status === "running";

  return (
    <div
      onClick={() =>
        navigate(isLive ? `/monitor/${run.run_id}` : `/report/${run.run_id}`)
      }
      className={cn(
        "relative glass glass-subtle rounded-lg px-4 py-3 flex items-center gap-3 cursor-pointer",
        "transition-all duration-150 hover:glass-elevated hover:-translate-y-0.5",
        "specular-top inset-glow",
        className
      )}
    >
      <span
        className={cn(
          "absolute left-0 top-[20%] bottom-[20%] w-0.5 rounded-r",
          bar,
          isLive && "animate-bar-breathe"
        )}
      />

      <StatusDot status={run.status} />

      <span className="flex-1 text-sm font-[510] text-aria-text2 truncate">
        {run.topic ?? run.message ?? run.run_id}
      </span>

      <span className="text-sm font-[590] text-aria-text1 w-10 text-right tabular-nums">
        {run.total_documents != null ? run.total_documents.toLocaleString() : "—"}
      </span>

      <span className="text-[11px] text-aria-text4 w-16 text-right">
        {run.updated_at
          ? formatDistanceToNow(new Date(run.updated_at), { addSuffix: false })
          : "—"}
      </span>
    </div>
  );
}
