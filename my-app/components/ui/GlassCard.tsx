import * as React from "react"
import { cn } from "@/lib/utils"

interface GlassCardProps extends React.HTMLAttributes<HTMLDivElement> {
    hoverEffect?: boolean
}

const GlassCard = React.forwardRef<HTMLDivElement, GlassCardProps>(
    ({ className, hoverEffect = true, children, ...props }, ref) => {
        return (
            <div
                ref={ref}
                className={cn(
                    "relative overflow-hidden bg-surface-container transition-all duration-500 ease-out",
                    hoverEffect && "hover:bg-surface-container-high",
                    className
                )}
                {...props}
            >
                <div className="relative z-10">
                    {children}
                </div>
            </div>
        )
    }
)
GlassCard.displayName = "GlassCard"

export { GlassCard }
