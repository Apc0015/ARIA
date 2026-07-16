import * as React from "react"
import { Slot } from "@radix-ui/react-slot"
import { cva, type VariantProps } from "class-variance-authority"

import { cn } from "@/lib/utils"

const buttonVariants = cva(
  "inline-flex items-center justify-center gap-2 whitespace-nowrap transition-all duration-150 focus-visible:outline-none disabled:pointer-events-none disabled:opacity-50 [&_svg]:pointer-events-none [&_svg]:size-4 [&_svg]:shrink-0",
  {
    variants: {
      variant: {
        ghost:
          "bg-black/[0.045] dark:bg-white/10 text-aria-text1 rounded-lg hover:bg-black/[0.08] dark:hover:bg-white/[0.16] active:scale-[0.98] focus-visible:shadow-elevation-focus",
        subtle:
          "bg-black/[0.03] dark:bg-white/[0.06] text-aria-text2 rounded-lg hover:bg-black/[0.06] dark:hover:bg-white/10 active:scale-[0.98] focus-visible:shadow-elevation-focus",
        primary:
          "bg-aria-accent text-white rounded-full hover:bg-aria-accent-hover active:scale-[0.98] focus-visible:shadow-elevation-focus",
        icon:
          "bg-black/[0.045] dark:bg-white/10 text-aria-text1 rounded-full hover:bg-black/[0.08] dark:hover:bg-white/[0.16] active:scale-[0.95] focus-visible:shadow-elevation-focus",
        pill:
          "bg-transparent text-aria-text2 border border-[var(--aria-border)] rounded-pill hover:bg-black/[0.03] dark:hover:bg-white/[0.06] active:scale-[0.98] focus-visible:shadow-elevation-focus",
        toolbar:
          "bg-black/[0.04] dark:bg-white/[0.08] text-aria-text3 rounded-md hover:bg-black/[0.07] dark:hover:bg-white/[0.14] focus-visible:shadow-elevation-focus text-label font-medium",
        destructive:
          "bg-destructive text-destructive-foreground shadow-sm hover:bg-destructive/90",
        outline:
          "border border-input bg-background shadow-sm hover:bg-accent hover:text-accent-foreground",
        secondary:
          "bg-secondary text-secondary-foreground shadow-sm hover:bg-secondary/80",
        link: "text-primary underline-offset-4 hover:underline",
      },
      size: {
        default: "h-9 px-4 py-2 text-body",
        sm: "h-8 px-3 text-xs",
        lg: "h-10 px-8",
        icon: "h-9 w-9",
      },
    },
    defaultVariants: {
      variant: "ghost",
      size: "default",
    },
  }
)

export interface ButtonProps
  extends React.ButtonHTMLAttributes<HTMLButtonElement>,
    VariantProps<typeof buttonVariants> {
  asChild?: boolean
}

const Button = React.forwardRef<HTMLButtonElement, ButtonProps>(
  ({ className, variant, size, asChild = false, ...props }, ref) => {
    const Comp = asChild ? Slot : "button"
    return (
      <Comp
        className={cn(buttonVariants({ variant, size, className }))}
        ref={ref}
        {...props}
      />
    )
  }
)
Button.displayName = "Button"

// eslint-disable-next-line react-refresh/only-export-components
export { Button, buttonVariants }
