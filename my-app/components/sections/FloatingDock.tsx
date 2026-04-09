"use client"

import { useState, useEffect, useRef } from "react"
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

export function FloatingDock() {
    const [activeSection, setActiveSection] = useState("")
    const scrollTimeoutRef = useRef<NodeJS.Timeout | null>(null)

    useEffect(() => {
        const sections = dockItems.map(item => item.href.replace("#", ""))

        const getActiveSection = () => {
            let closestSection = ""
            let minDistance = Infinity

            for (const id of sections) {
                const el = document.getElementById(id)
                if (!el) continue

                const rect = el.getBoundingClientRect()
                const distance = Math.abs(rect.top)

                if (distance < minDistance && rect.top <= window.innerHeight * 0.5) {
                    minDistance = distance
                    closestSection = id
                }
            }

            setActiveSection(closestSection)
        }

        getActiveSection()

        const handleScroll = () => {
            if (scrollTimeoutRef.current) {
                clearTimeout(scrollTimeoutRef.current)
            }
            scrollTimeoutRef.current = setTimeout(getActiveSection, 16)
        }

        window.addEventListener("scroll", handleScroll, { passive: true })
        window.addEventListener("resize", getActiveSection, { passive: true })

        return () => {
            window.removeEventListener("scroll", handleScroll)
            window.removeEventListener("resize", getActiveSection)
            if (scrollTimeoutRef.current) {
                clearTimeout(scrollTimeoutRef.current)
            }
        }
    }, [])

    return (
        <motion.div
            initial={{ y: 100, opacity: 0 }}
            animate={{ y: 0, opacity: 1 }}
            transition={{ duration: 0.6, delay: 0.4, ease: "easeOut" }}
            className="fixed bottom-6 left-1/2 -translate-x-1/2 z-50"
        >
            <nav className="rounded-full border border-white/10 bg-neutral-900/60 backdrop-blur-xl shadow-[0_20px_50px_rgba(70,145,255,0.1)] px-3 py-3 flex items-center gap-1">
                {dockItems.map((item) => {
                    const section = item.href.replace("#", "")
                    const isActive = activeSection === section
                    return (
                        <Link
                            key={item.href}
                            href={item.href}
                            onClick={() => setActiveSection(section)}
                            className={cn(
                                "flex items-center gap-2 px-6 py-2 rounded-full font-display text-xs tracking-wider transition-all duration-300",
                                isActive
                                    ? "bg-blue-500/20 text-blue-400"
                                    : "text-neutral-500 hover:bg-white/5"
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
