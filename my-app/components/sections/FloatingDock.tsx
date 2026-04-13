"use client"

import { useEffect, useState } from "react"
import { motion } from "framer-motion"
import Link from "next/link"
import { cn } from "@/lib/utils"
import { LayoutGrid, Cpu, User, Mail } from "lucide-react"

const dockItems = [
    { label: "Work", href: "#projects", icon: <LayoutGrid className="w-4 h-4" /> },
    { label: "Stack", href: "#skills", icon: <Cpu className="w-4 h-4" /> },
    { label: "About", href: "#about", icon: <User className="w-4 h-4" /> },
    { label: "Inquiry", href: "#contact", icon: <Mail className="w-4 h-4" /> },
]

const allSections = ["hero", ...dockItems.map(item => item.href.replace("#", ""))]

function useActiveSection() {
    const [activeSection, setActiveSection] = useState("")

    useEffect(() => {
        const observer = new IntersectionObserver(
            (entries) => {
                const intersecting = entries
                    .filter(entry => entry.isIntersecting)
                    .sort((a, b) => {
                        const rectA = a.boundingClientRect
                        const rectB = b.boundingClientRect
                        return Math.abs(rectA.top) - Math.abs(rectB.top)
                    })

                if (intersecting.length > 0) {
                    const topSection = intersecting[0].target.id
                    if (topSection === "hero") {
                        setActiveSection("")
                    } else {
                        setActiveSection(topSection)
                    }
                }
            },
            {
                rootMargin: "-50% 0px -50% 0px",
                threshold: 0,
            }
        )

        allSections.forEach(id => {
            const el = document.getElementById(id)
            if (el) observer.observe(el)
        })

        return () => observer.disconnect()
    }, [])

    return activeSection
}

export function FloatingDock() {
    const activeSection = useActiveSection()

    return (
        <>
            {/* Mobile bottom nav - shows on small screens, hidden on lg+ (tablet/desktop) */}
            <motion.div
                initial={{ y: 100, opacity: 0 }}
                animate={{ y: 0, opacity: 1 }}
                transition={{ duration: 0.6, delay: 0.4, ease: "easeOut" }}
                className="fixed bottom-0 left-0 right-0 z-50 lg:hidden border-t border-white/[0.15] bg-[#131313]/80 backdrop-blur-xl"
            >
                <nav className="flex items-center justify-around px-2 py-2">
                    {dockItems.map((item) => {
                        const section = item.href.replace("#", "")
                        const isActive = activeSection === section
                        return (
                            <Link
                                key={item.href}
                                href={item.href}
                                className={cn(
                                    "flex flex-col items-center gap-1 p-2 rounded-lg transition-all duration-300",
                                    isActive
                                        ? "bg-primary-container text-on-primary-container"
                                        : "text-on-surface-variant hover:bg-white/[0.05]"
                                )}
                            >
                                {item.icon}
                                <span className="text-[0.625rem] font-display tracking-wider">{item.label}</span>
                            </Link>
                        )
                    })}
                </nav>
            </motion.div>

            {/* Desktop dock - hidden on small screens, shows on lg+ (tablet/desktop) */}
            <motion.div
                initial={{ y: 100, opacity: 0 }}
                animate={{ y: 0, opacity: 1 }}
                transition={{ duration: 0.6, delay: 0.4, ease: "easeOut" }}
                className="fixed bottom-6 left-1/2 -translate-x-1/2 z-50 hidden lg:flex"
            >
                <nav className="rounded-full border border-white/[0.15] bg-[#131313]/60 backdrop-blur-[12px] shadow-[0_20px_50px_rgba(70,145,255,0.04)] px-3 py-3 flex items-center gap-1">
                    {dockItems.map((item) => {
                        const section = item.href.replace("#", "")
                        const isActive = activeSection === section
                        return (
                            <Link
                                key={item.href}
                                href={item.href}
                                className={cn(
                                    "flex items-center gap-2 px-6 py-2 rounded-full font-display text-xs tracking-wider transition-all duration-300",
                                    isActive
                                        ? "bg-[#4691ff] text-white shadow-[0_0_20px_rgba(70,145,255,0.4)]"
                                        : "text-[#a0a0a0] hover:bg-white/[0.08]"
                                )}
                            >
                                {item.icon}
                                <span>{item.label}</span>
                            </Link>
                        )
                    })}
                </nav>
            </motion.div>
        </>
    )
}