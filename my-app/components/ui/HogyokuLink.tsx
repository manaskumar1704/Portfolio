import * as React from "react"
import Link from "next/link"
import { cn } from "@/lib/utils"

interface HogyokuLinkProps extends React.AnchorHTMLAttributes<HTMLAnchorElement> {
    href: string
    active?: boolean
}

const HogyokuLink = ({ className, href, active, children, ...props }: HogyokuLinkProps) => {
    return (
        <Link
            href={href}
            className={cn(
                "relative inline-block text-sm font-mono tracking-widest text-muted-foreground transition-colors duration-300 hover:text-hogyoku group",
                active && "text-hogyoku text-glow-cyan",
                className
            )}
            {...props}
        >
            <span className="relative z-10">{children}</span>

            {/* Underline expansion effect */}
            <span
                className={cn(
                    "absolute bottom-0 left-0 w-0 h-[1px] bg-hogyoku transition-all duration-300 group-hover:w-full box-shadow-[0_0_8px_var(--hogyoku)]",
                    active && "w-full"
                )}
            />
        </Link>
    )
}
HogyokuLink.displayName = "HogyokuLink"

export { HogyokuLink }
