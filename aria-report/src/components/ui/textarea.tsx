import * as React from "react"

import { cn } from "@/lib/utils"

const Textarea = React.forwardRef<
  HTMLTextAreaElement,
  React.ComponentProps<"textarea">
>(({ className, ...props }, ref) => {
  return (
    <textarea
      className={cn(
        "flex min-h-[60px] w-full rounded-md border border-[var(--aria-border)] bg-aria-surface px-3 py-2 text-body text-aria-text1 placeholder:text-aria-text3 transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-aria-accent/60 disabled:cursor-not-allowed disabled:opacity-50 resize-none",
        className
      )}
      ref={ref}
      {...props}
    />
  )
})
Textarea.displayName = "Textarea"

export { Textarea }
