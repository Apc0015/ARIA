import { cn } from "@/lib/utils";
import { type HTMLAttributes, forwardRef } from "react";

interface GlassCardProps extends HTMLAttributes<HTMLDivElement> {
  elevated?: boolean;
  featured?: boolean;
}

/**
 * GlassCard — Linear-style elevated surface.
 * Elevation via background luminance stepping (not shadows):
 *   default: rgba(255,255,255,0.03) — Level 2 surface
 *   elevated: rgba(255,255,255,0.05) — Level 3 surface
 */
export const GlassCard = forwardRef<HTMLDivElement, GlassCardProps>(
  ({ className, perspective = true, elevated = false, featured = false, children, ...props }, ref) => (
    <div
      ref={ref}
      className={cn(
        "relative transition-all duration-200",
        featured ? "rounded-xl" : "rounded-lg",
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
