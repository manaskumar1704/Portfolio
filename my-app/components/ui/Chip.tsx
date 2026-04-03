import * as React from "react"
import { cn } from "@/lib/utils"

interface ChipProps extends React.HTMLAttributes<HTMLSpanElement> {
    label: string
}

const Chip = React.forwardRef<HTMLSpanElement, ChipProps>(
    ({ className, label, ...props }, ref) => {
        return (
            <span
                ref={ref}
                className={cn(
                    "inline-flex items-center px-3 py-1.5 bg-surface-container-highest text-on-surface-variant font-display text-xs tracking-wider uppercase",
                    "transition-colors duration-300 hover:text-on-surface hover:bg-surface-container-highest/80",
                    className
                )}
                {...props}
            >
                {label}
            </span>
        )
    }
)
Chip.displayName = "Chip"

export { Chip }
