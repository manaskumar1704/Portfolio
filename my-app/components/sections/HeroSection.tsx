"use client"

import { motion } from "framer-motion"
import { ArrowRight } from "lucide-react"

export function HeroSection() {
    return (
        <section className="relative min-h-screen flex flex-col justify-center overflow-hidden px-6 md:px-12 lg:px-24 pt-24 pb-16">
            {/* Subtle ambient glow */}
            <div className="absolute top-[-10%] right-[-5%] w-[40%] h-[40%] bg-primary/5 blur-[150px] rounded-full pointer-events-none" />

            <div className="relative z-10 max-w-7xl mx-auto w-full">
                {/* Top label */}
                <motion.div
                    initial={{ opacity: 0, y: 16 }}
                    animate={{ opacity: 1, y: 0 }}
                    transition={{ duration: 0.6, ease: "easeOut" }}
                >
                    <span className="text-label-md text-on-surface-variant tracking-[0.2em]">
                        Systems Architect & Interface Engineer
                    </span>
                </motion.div>

                {/* Main headline - asymmetrical, pushed left */}
                <motion.div
                    initial={{ opacity: 0, y: 24 }}
                    animate={{ opacity: 1, y: 0 }}
                    transition={{ duration: 0.8, delay: 0.15, ease: "easeOut" }}
                    className="mt-6 md:mt-10"
                >
                    <h1 className="text-display-lg md:text-display-lg lg:text-[4.5rem] leading-[0.95] tracking-[-0.04em] text-on-surface">
                        CRAFTING
                        <br />
                        <span className="text-primary">DIGITAL</span>
                        <br />
                        MONOLITHS.
                    </h1>
                </motion.div>

                {/* Asymmetrical content row */}
                <div className="mt-12 md:mt-16 flex flex-col md:flex-row gap-12 md:gap-24">
                    {/* Left: Description */}
                    <motion.div
                        initial={{ opacity: 0, y: 20 }}
                        animate={{ opacity: 1, y: 0 }}
                        transition={{ duration: 0.7, delay: 0.35, ease: "easeOut" }}
                        className="md:w-[45%]"
                    >
                        <p className="text-body-lg text-on-surface-variant leading-relaxed max-w-md">
                            Developing high-performance spatial interfaces
                            and scalable architectural backends. Where
                            technical precision meets editorial design.
                        </p>
                    </motion.div>

                    {/* Right: Current Focus */}
                    <motion.div
                        initial={{ opacity: 0, y: 20 }}
                        animate={{ opacity: 1, y: 0 }}
                        transition={{ duration: 0.7, delay: 0.5, ease: "easeOut" }}
                        className="md:w-[40%] md:ml-auto"
                    >
                        <div className="bg-surface-container p-6 md:p-8">
                            <span className="text-label-sm text-on-surface-variant/60 tracking-wider">
                                CURRENT FOCUS
                            </span>
                            <p className="text-body-md text-on-surface mt-3 leading-relaxed">
                                WebGPU / Distributed Systems
                            </p>
                        </div>
                    </motion.div>
                </div>

                {/* CTA Row */}
                <motion.div
                    initial={{ opacity: 0, y: 20 }}
                    animate={{ opacity: 1, y: 0 }}
                    transition={{ duration: 0.7, delay: 0.65, ease: "easeOut" }}
                    className="mt-12 md:mt-16 flex items-center gap-6"
                >
                    <button
                        onClick={() => document.getElementById('works')?.scrollIntoView({ behavior: 'smooth' })}
                        className="group inline-flex items-center gap-3 px-6 py-3 bg-primary-container text-on-primary-container font-display text-sm font-medium tracking-wide transition-transform duration-300 hover:scale-[1.02]"
                    >
                        VIEW WORK
                        <ArrowRight className="w-4 h-4 transition-transform duration-300 group-hover:translate-x-1" />
                    </button>

                    <a
                        href="#contact"
                        className="text-label-md text-on-surface-variant hover:text-on-surface transition-colors duration-300"
                    >
                        CONNECT
                    </a>
                </motion.div>
            </div>
        </section>
    )
}
