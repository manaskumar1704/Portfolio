"use client"

import { motion } from "framer-motion"

const stats = [
    { label: "Projects Shipped", value: "4 and incoming" },
    { label: "Agents Built", value: "3 and building" },
    { label: "LLM APIs Used", value: "Looking out for" },
]

export function AboutSection() {
    return (
        <section id="about" className="py-24 px-6 md:px-12 lg:px-24 relative">
            <div className="max-w-7xl mx-auto">
                <div className="grid grid-cols-1 sm:grid-cols-2 gap-8 sm:gap-12 md:gap-24">
                    <motion.div
                        initial={{ opacity: 0, y: 20 }}
                        whileInView={{ opacity: 1, y: 0 }}
                        viewport={{ once: true }}
                        transition={{ duration: 0.6 }}
                    >
                        <span className="text-label-sm text-on-surface-variant tracking-[0.3em]">
                            ABOUT
                        </span>
                        <p className="text-body-lg text-on-surface-variant mt-6 leading-relaxed">
                            I&#39;m a Computer Science graduate from Vellore Institute of Technology, specializing in 
                            LLM orchestration, RAG systems, and multi-agent architectures. I build 
                            AI systems that are production-ready — observable, evaluated, and 
                            deployable — not just demos. Actively seeking roles where agentic AI 
                            meets real-world impact at scale.
                        </p>
                    </motion.div>

                    <motion.div
                        initial={{ opacity: 0, y: 20 }}
                        whileInView={{ opacity: 1, y: 0 }}
                        viewport={{ once: true }}
                        transition={{ duration: 0.6, delay: 0.15 }}
                        className="bg-surface-container p-6"
                    >
                        <div className="grid grid-cols-1 sm:grid-cols-3 gap-6">
                            {stats.map((stat, index) => (
                                <div key={index} className="border-l-2 border-primary/30 pl-4">
                                    <span className="text-label-sm text-on-surface-variant/60 block mb-1">
                                        {stat.label}
                                    </span>
                                    <span className="text-2xl md:text-3xl font-mono text-on-surface">
                                        {stat.value}
                                    </span>
                                </div>
                            ))}
                        </div>
                    </motion.div>
                </div>
            </div>
        </section>
    )
}
