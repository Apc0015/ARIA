import { cn } from "@/lib/utils";
import { type HTMLAttributes, forwardRef } from "react";

interface GlassCardProps extends HTMLAttributes<HTMLDivElement> {
  perspective?: boolean;
  elevated?: boolean;
  featured?: boolean;
}

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
