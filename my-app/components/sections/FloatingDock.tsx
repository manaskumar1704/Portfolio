"use client"

import { useState, useEffect } from "react"
import { motion } from "framer-motion"
import Link from "next/link"
import { cn } from "@/lib/utils"
import { Grid2X2, Cpu, User, Mail } from "lucide-react"

const dockItems = [
    { label: "WORK", href: "#works", icon: <Grid2X2 className="w-4 h-4" /> },
    { label: "STACK", href: "#stack", icon: <Cpu className="w-4 h-4" /> },
    { label: "ABOUT", href: "#about", icon: <User className="w-4 h-4" /> },
    { label: "INQUIRY", href: "#contact", icon: <Mail className="w-4 h-4" /> },
]

export function FloatingDock() {
    const [activeSection, setActiveSection] = useState("")

    useEffect(() => {
        const handleScroll = () => {
            const sections = dockItems.map(item => item.href.replace("#", ""))
            for (let i = sections.length - 1; i >= 0; i--) {
                const el = document.getElementById(sections[i])
                if (el && el.getBoundingClientRect().top <= 200) {
                    setActiveSection(sections[i])
                    break
                }
            }
        }

        window.addEventListener("scroll", handleScroll, { passive: true })
        return () => window.removeEventListener("scroll", handleScroll)
    }, [])

    return (
        <motion.div
            initial={{ y: 100, opacity: 0 }}
            animate={{ y: 0, opacity: 1 }}
            transition={{ duration: 0.6, delay: 0.4, ease: "easeOut" }}
            className="fixed bottom-6 left-1/2 -translate-x-1/2 z-50"
        >
            <nav className="glass-panel rounded-xl px-2 py-2 flex items-center gap-1">
                {dockItems.map((item) => {
                    const isActive = activeSection === item.href.replace("#", "")
                    return (
                        <Link
                            key={item.href}
                            href={item.href}
                            className={cn(
                                "relative flex items-center gap-2 px-4 py-2.5 rounded-lg font-display text-xs tracking-wider uppercase transition-all duration-300",
                                isActive
                                    ? "bg-primary-container text-on-primary-container"
                                    : "text-on-surface-variant hover:text-on-surface hover:bg-surface-container-high"
                            )}
                        >
                            {item.icon}
                            <span className="hidden sm:inline">{item.label}</span>
                        </Link>
                    )
                })}
            </nav>
        </motion.div>
    )
}
