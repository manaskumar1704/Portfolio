import * as React from "react"
import { cn } from "@/lib/utils"

interface GlassCardProps extends React.HTMLAttributes<HTMLDivElement> {
    hoverEffect?: boolean
    intensity?: "low" | "medium" | "high"
}

const GlassCard = React.forwardRef<HTMLDivElement, GlassCardProps>(
    ({ className, hoverEffect = true, intensity = "medium", children, ...props }, ref) => {

        const intensityStyles = {
            low: "bg-white/[0.02] border-white/[0.05]",
            medium: "bg-white/[0.03] border-white/[0.08]",
            high: "bg-white/[0.05] border-white/[0.10]",
        }

        return (
            <div
                ref={ref}
                className={cn(
                    "relative overflow-hidden rounded-xl backdrop-blur-md transition-all duration-500 ease-out border shadow-lg",
                    intensityStyles[intensity],
                    hoverEffect && "hover:bg-white/[0.06] hover:border-reiatsu/30 hover:shadow-[0_0_30px_-10px_var(--reiatsu)] hover:-translate-y-1",
                    className
                )}
                {...props}
            >
                {/* Subtle gradient overlay for depth */}
                <div className="absolute inset-0 bg-gradient-to-br from-white/[0.02] to-transparent pointer-events-none" />

                {/* Content */}
                <div className="relative z-10">
                    {children}
                </div>
            </div>
        )
    }
)
GlassCard.displayName = "GlassCard"

export { GlassCard }
