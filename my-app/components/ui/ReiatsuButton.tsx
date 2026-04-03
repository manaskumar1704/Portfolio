"use client"

import * as React from "react"
import { motion, HTMLMotionProps } from "framer-motion"
import { cn } from "@/lib/utils"

interface ReiatsuButtonProps extends HTMLMotionProps<"button"> {
    variant?: "primary" | "secondary" | "ghost"
    glow?: boolean
    children?: React.ReactNode
}

const ReiatsuButton = React.forwardRef<HTMLButtonElement, ReiatsuButtonProps>(
    ({ className, variant = "primary", glow = true, children, ...props }, ref) => {

        // Base styles
        const baseStyles = "relative inline-flex items-center justify-center px-8 py-3 overflow-hidden font-serif font-bold tracking-wider uppercase transition-all duration-300 rounded-md group focus:outline-none focus:ring-2 focus:ring-reiatsu focus:ring-offset-2 focus:ring-offset-obsidian"

        // Variant styles
        const variants = {
            primary: "bg-reiatsu text-white border border-transparent hover:bg-violet-700",
            secondary: "bg-transparent text-white border border-reiatsu/50 hover:bg-reiatsu/10",
            ghost: "bg-transparent text-gray-300 hover:text-white hover:bg-white/5",
        }

        return (
            <motion.button
                ref={ref}
                className={cn(baseStyles, variants[variant], className)}
                whileHover={{ scale: 1.02 }}
                whileTap={{ scale: 0.98 }}
                {...props}
            >
                {/* Glow Effect for Primary */}
                {variant === 'primary' && glow && (
                    <span className="absolute inset-0 w-full h-full bg-gradient-to-br from-violet-600 to-indigo-900 opacity-20 blur-xl group-hover:opacity-40 transition-opacity duration-300" />
                )}

                {/* Shine Effect */}
                <span className="absolute inset-0 w-full h-full -translate-x-full group-hover:translate-x-full transition-transform duration-700 ease-in-out bg-gradient-to-r from-transparent via-white/10 to-transparent" />

                {/* Content */}
                <span className="relative z-10 flex items-center gap-2">
                    {children}
                </span>
            </motion.button>
        )
    }
)
ReiatsuButton.displayName = "ReiatsuButton"

export { ReiatsuButton }
