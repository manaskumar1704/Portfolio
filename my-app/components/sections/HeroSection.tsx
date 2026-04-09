"use client"

import { useCallback } from "react"
import { motion } from "framer-motion"
import { ArrowRight, Github, Linkedin } from "lucide-react"

export function HeroSection() {
    const scrollToProjects = useCallback(() => {
        document.getElementById('projects')?.scrollIntoView({ behavior: 'smooth' })
    }, [])
    return (
        <section className="relative min-h-screen flex flex-col justify-center overflow-hidden px-6 md:px-12 lg:px-24 pt-24 pb-16">
            <div className="relative z-10 max-w-7xl mx-auto w-full">
                <div className="flex flex-col lg:flex-row items-center lg:justify-between gap-8">
                    <div className="flex-1 max-w-2xl">
                        <motion.div
                            initial={{ opacity: 0, y: 16 }}
                            animate={{ opacity: 1, y: 0 }}
                            transition={{ duration: 0.6, ease: "easeOut" }}
                            className="flex items-center gap-2"
                        >
                            <span className="w-2 h-2 bg-green-500 rounded-full animate-pulse" />
                            <span className="text-label-md text-on-surface-variant tracking-[0.2em]">
                                AVAILABLE FOR WORK
                            </span>
                        </motion.div>

                        <motion.div
                            initial={{ opacity: 0, y: 24 }}
                            animate={{ opacity: 1, y: 0 }}
                            transition={{ duration: 0.8, delay: 0.15, ease: "easeOut" }}
                            className="mt-6 md:mt-10"
                        >
                            <h1 className="font-display text-6xl md:text-7xl lg:text-8xl leading-[0.95] tracking-[-0.04em] uppercase text-on-surface">
                                Manas<br />
                                <span className="text-primary">Kumar</span>
                            </h1>
                        </motion.div>

                        <motion.div
                            initial={{ opacity: 0, y: 24 }}
                            animate={{ opacity: 1, y: 0 }}
                            transition={{ duration: 0.8, delay: 0.25, ease: "easeOut" }}
                            className="mt-8 md:mt-12"
                        >
                            <h2 className="font-display text-4xl md:text-5xl lg:text-6xl leading-[0.95] tracking-[-0.04em] uppercase text-on-surface">
                                Building Production Grade<br />
                                Agentic Systems.
                            </h2>
                        </motion.div>

                        <motion.div
                            initial={{ opacity: 0, y: 20 }}
                            animate={{ opacity: 1, y: 0 }}
                            transition={{ duration: 0.7, delay: 0.35, ease: "easeOut" }}
                            className="mt-6 md:mt-8"
                        >
                            <p className="text-body-lg text-on-surface-variant max-w-xl">
                                Open To
                            </p>
                            <p className="text-xl md:text-2xl font-display text-primary mt-1">
                                GenAI . Agentic . Full-Stack . SDE
                            </p>
                        </motion.div>

                        <motion.div
                            initial={{ opacity: 0, y: 20 }}
                            animate={{ opacity: 1, y: 0 }}
                            transition={{ duration: 0.7, delay: 0.45, ease: "easeOut" }}
                            className="mt-10 md:mt-14 flex items-center gap-6 flex-wrap"
                        >
                            <button
                                onClick={scrollToProjects}
                                suppressHydrationWarning
                                className="group inline-flex items-center gap-3 px-6 py-3 bg-primary-container text-on-primary-container font-display text-sm font-medium tracking-wide transition-transform duration-300 hover:scale-[1.02]"
                            >
                                View Projects
                                <ArrowRight className="w-4 h-4 transition-transform duration-300 group-hover:translate-x-1" />
                            </button>

                            <a
                                href="/Manas_Kumar_Resume _SDE.pdf"
                                target="_blank"
                                rel="noopener noreferrer"
                                className="group inline-flex items-center gap-3 px-6 py-3 border border-white/10 text-on-surface font-display text-sm font-medium tracking-wide transition-all duration-300 hover:bg-white/5"
                            >
                                Download Resume
                            </a>

                            <a
                                href="https://github.com/manaskumar1704"
                                target="_blank"
                                rel="noopener noreferrer"
                                className="p-3 text-on-surface-variant hover:text-on-surface transition-colors duration-300"
                            >
                                <Github className="w-5 h-5" />
                            </a>

                            <a
                                href="https://www.linkedin.com/in/manas-kumar1/"
                                target="_blank"
                                rel="noopener noreferrer"
                                className="p-3 text-on-surface-variant hover:text-on-surface transition-colors duration-300"
                            >
                                <Linkedin className="w-5 h-5" />
                            </a>
                        </motion.div>
                    </div>

                    <motion.div
                        initial={{ opacity: 0, scale: 0.95 }}
                        animate={{ opacity: 1, scale: 1 }}
                        transition={{ duration: 0.8, delay: 0.3 }}
                        className="hidden lg:block flex-shrink-0"
                    >
                        <div className="relative w-[280px] h-[350px] overflow-hidden rounded-lg group">
                            <img
                                src="/images/projects/my_image.png"
                                alt="Manas Kumar"
                                className="w-full h-full object-cover object-top grayscale opacity-80 group-hover:grayscale-0 group-hover:scale-105 group-hover:opacity-100 transition-all duration-700"
                            />
                        </div>
                    </motion.div>
                </div>
            </div>
        </section>
    )
}
