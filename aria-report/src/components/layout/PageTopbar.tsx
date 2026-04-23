import { ReactNode } from "react";
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
        "h-11 flex-shrink-0 flex items-center gap-2 px-5 border-b border-white/[0.05]",
        className
      )}
    >
      <span className="text-[13px] font-[510] text-aria-text1">{title}</span>
      {subtitle && (
        <>
          <span className="text-aria-text4">/</span>
          <span className="text-[13px] text-aria-text4 truncate max-w-[200px]">{subtitle}</span>
        </>
      )}
      <div className="flex-1" />
      {action}
    </header>
  );
}
