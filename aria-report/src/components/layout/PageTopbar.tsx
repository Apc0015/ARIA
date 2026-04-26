import { type ReactNode } from "react";
import { cn } from "@/lib/utils";

interface PageTopbarProps {
  title: string;
  subtitle?: string;
  action?: ReactNode;
  className?: string;
}

export function PageTopbar({ title, subtitle, action, className }: PageTopbarProps) {
  return (
    <header
      className={cn(
        "h-12 flex-shrink-0 flex items-center gap-2 px-5",
        "border-b border-[var(--aria-border-subtle)]",
        "bg-[var(--aria-panel)]/80 backdrop-blur-sm",
        className
      )}
    >
      <span className="text-[13px] font-[590] text-aria-text1 tracking-caption">{title}</span>
      {subtitle && (
        <>
          <span className="text-aria-text4 text-[13px] font-[510]">/</span>
          <span className="text-[13px] font-[510] text-aria-text4 truncate max-w-[240px]">{subtitle}</span>
        </>
      )}
      <div className="flex-1" />
      {action}
    </header>
  );
}
