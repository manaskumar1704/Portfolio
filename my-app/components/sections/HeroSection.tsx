"use client"

import { motion } from "framer-motion"
import { ReiatsuButton } from "../ui/ReiatsuButton"
import { ArrowDown } from "lucide-react"

export function HeroSection() {
    return (
        <section className="relative h-screen flex flex-col items-center justify-center overflow-hidden">
            {/* Abstract Energy Flow Background */}
            <div className="absolute inset-0 w-full h-full bg-obsidian">
                <div className="absolute top-[-20%] left-[-10%] w-[50%] h-[50%] bg-reiatsu/5 blur-[120px] rounded-full mix-blend-screen animate-pulse-slow" />
                <div className="absolute bottom-[-20%] right-[-10%] w-[50%] h-[50%] bg-hogyoku/5 blur-[120px] rounded-full mix-blend-screen animate-pulse-slow delay-1000" />
            </div>

            {/* Grid overlay */}
            <div className="absolute inset-0 bg-[url('/grid.svg')] opacity-[0.03]" />

            <div className="relative z-10 px-4 text-center max-w-4xl mx-auto">
                <motion.div
                    initial={{ opacity: 0, y: 20 }}
                    animate={{ opacity: 1, y: 0 }}
                    transition={{ duration: 0.8, ease: "easeOut" }}
                >
                    <span className="inline-block py-1 px-3 mb-6 text-sm font-mono text-hogyoku tracking-widest border border-hogyoku/20 rounded-full bg-hogyoku/5 backdrop-blur-sm">
                        SYSTEM.ONLINE // WELCOME
                    </span>
                </motion.div>

                <motion.h1
                    initial={{ opacity: 0, scale: 0.9 }}
                    animate={{ opacity: 1, scale: 1 }}
                    transition={{ duration: 1, delay: 0.2 }}
                    className="text-5xl md:text-7xl lg:text-8xl font-serif font-bold tracking-tight text-white mb-6 text-glow-cyan"
                >
                    Architecting <br />
                    <span className="text-transparent bg-clip-text bg-gradient-to-r from-white via-slate-200 to-slate-400">
                        Digital Realities
                    </span>
                </motion.h1>

                <motion.p
                    initial={{ opacity: 0 }}
                    animate={{ opacity: 1 }}
                    transition={{ duration: 1, delay: 0.6 }}
                    className="text-lg md:text-xl text-muted-foreground max-w-2xl mx-auto mb-10 font-mono"
                >
                    Shattering the boundary between illusion and code.
                    Building immersive experiences that wield power and elegance.
                </motion.p>

                <motion.div
                    initial={{ opacity: 0, y: 20 }}
                    animate={{ opacity: 1, y: 0 }}
                    transition={{ duration: 0.8, delay: 0.8 }}
                    className="flex flex-col sm:flex-row items-center justify-center gap-4"
                >
                    <ReiatsuButton onClick={() => document.getElementById('projects')?.scrollIntoView({ behavior: 'smooth' })}>
                        Explore Works
                    </ReiatsuButton>

                    <a href="#contact" className="px-8 py-3 text-sm font-mono text-gray-400 hover:text-white transition-colors">
                        Init_Contact_Protocol()
                    </a>
                </motion.div>
            </div>

            {/* Scroll Indicator */}
            <motion.div
                initial={{ opacity: 0 }}
                animate={{ opacity: 1 }}
                transition={{ delay: 1.5, duration: 1 }}
                className="absolute bottom-10 left-1/2 -translate-x-1/2"
            >
                <motion.div
                    animate={{ y: [0, 10, 0] }}
                    transition={{ repeat: Infinity, duration: 2 }}
                    className="text-muted-foreground/50"
                >
                    <ArrowDown className="w-6 h-6" />
                </motion.div>
            </motion.div>
        </section>
    )
}
