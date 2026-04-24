import { cn } from "@/lib/utils";
import { type HTMLAttributes, forwardRef } from "react";

interface GlassCardProps extends HTMLAttributes<HTMLDivElement> {
  perspective?: boolean;
  elevated?: boolean;
}

export const GlassCard = forwardRef<HTMLDivElement, GlassCardProps>(
  ({ className, perspective = true, elevated = false, children, ...props }, ref) => (
    <div
      ref={ref}
      className={cn(
        "relative rounded-[10px] transition-all duration-200",
        elevated ? "glass-elevated" : "glass",
        perspective && "perspective-card specular-top inset-glow",
        className
      )}
      {...props}
    >
      {children}
    </div>
  )
);
GlassCard.displayName = "GlassCard";
