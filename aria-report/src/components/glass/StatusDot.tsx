import { cn } from "@/lib/utils";
import type { RunStatus } from "@/types";

interface StatusDotProps {
  status: RunStatus;
  size?: "sm" | "md";
}

const statusConfig: Record<RunStatus, { color: string; glow: string; animate: boolean }> = {
  queued: { color: "bg-aria-text4", glow: "", animate: false },
  running: { color: "bg-aria-accent", glow: "status-glow-violet", animate: true },
  pending: { color: "bg-aria-text4", glow: "", animate: false },
  completed: { color: "bg-aria-success", glow: "status-glow-green", animate: false },
  failed: { color: "bg-red-500", glow: "", animate: false },
  cancelled: { color: "bg-aria-text4", glow: "", animate: false },
};

export function StatusDot({ status, size = "md" }: StatusDotProps) {
  const { color, glow, animate } = statusConfig[status] ?? statusConfig.pending;
  return (
    <span
      className={cn(
        "rounded-full flex-shrink-0 inline-block",
        size === "sm" ? "w-1.5 h-1.5" : "w-2 h-2",
        color,
        glow,
        animate && "animate-pulse-dot"
      )}
    />
  );
}
