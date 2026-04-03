"use client"

import { motion } from "framer-motion"

const capabilities = [
    {
        number: "01",
        title: "SYSTEMS ARCHITECTURE",
        description: "Designing scalable, high-concurrency backends. Expert in microservices, distributed databases, and real-time data streaming architectures."
    },
    {
        number: "02",
        title: "FRONTEND ENGINEERING",
        description: "Building performant, accessible, and cinematic web experiences. Specialist in GLSL, WebGPU, and complex state management."
    },
    {
        number: "03",
        title: "TECHNICAL CREATIVE",
        description: "Merging aesthetics with performance. Developing design systems that are as technically sound as they are visually striking."
    }
]

export function AboutSection() {
    return (
        <section id="about" className="py-24 px-6 md:px-12 lg:px-24 relative">
            <div className="max-w-7xl mx-auto">
                {/* Asymmetrical header */}
                <div className="flex flex-col md:flex-row md:items-end md:justify-between mb-20">
                    <div className="md:w-[60%] md:ml-[10%]">
                        <span className="text-label-sm text-primary tracking-[0.3em]">
                            PRINCIPAL CREATIVE TECHNOLOGIST
                        </span>
                        <h2 className="text-display-md md:text-[3.5rem] leading-[0.95] tracking-[-0.04em] text-on-surface mt-6">
                            ARCHITECTURE
                            <br />
                            <span className="text-on-surface-variant/30">IN MONOLITHIC</span>
                            <br />
                            SYSTEMS.
                        </h2>
                    </div>
                </div>

                {/* Content row */}
                <div className="flex flex-col md:flex-row gap-12 md:gap-24 mb-24">
                    <motion.div
                        initial={{ opacity: 0, y: 20 }}
                        whileInView={{ opacity: 1, y: 0 }}
                        viewport={{ once: true }}
                        transition={{ duration: 0.6 }}
                        className="md:w-[40%]"
                    >
                        <p className="text-body-lg text-on-surface-variant leading-relaxed">
                            Based at the intersection of aesthetic precision and technical rigor. I specialize in building digital artifacts that balance brutalist foundations with fluid interactivity.
                        </p>
                        <p className="text-body-md text-on-surface-variant/60 mt-6 leading-relaxed">
                            My approach is defined by the &ldquo;Architectural Monolith&rdquo; philosophy: creating singular, robust entities where every line of code serves a structural purpose. No decoration, only intent.
                        </p>
                    </motion.div>

                    <motion.div
                        initial={{ opacity: 0, y: 20 }}
                        whileInView={{ opacity: 1, y: 0 }}
                        viewport={{ once: true }}
                        transition={{ duration: 0.6, delay: 0.15 }}
                        className="md:w-[45%]"
                    >
                        <div className="bg-surface-container p-8">
                            <span className="text-label-sm text-on-surface-variant/40 tracking-wider">
                                CURRENT FOCUS
                            </span>
                            <p className="text-body-lg text-on-surface mt-4 leading-relaxed">
                                Engineering interfaces that feel like physical objects. High-density data visualization and GLSL-driven surfaces.
                            </p>
                        </div>
                    </motion.div>
                </div>

                {/* Capabilities list */}
                <div className="space-y-0">
                    {capabilities.map((cap, index) => (
                        <motion.div
                            key={index}
                            initial={{ opacity: 0, y: 16 }}
                            whileInView={{ opacity: 1, y: 0 }}
                            viewport={{ once: true }}
                            transition={{ duration: 0.5, delay: index * 0.1 }}
                            className="py-8 border-t border-white/[0.06]"
                        >
                            <div className="flex flex-col md:flex-row md:items-start gap-4 md:gap-12">
                                <span className="text-label-sm text-on-surface-variant/40 shrink-0">
                                    {cap.number}
                                </span>
                                <div className="flex-1">
                                    <h3 className="text-headline-sm text-on-surface mb-2">
                                        {cap.title}
                                    </h3>
                                    <p className="text-body-md text-on-surface-variant/70 leading-relaxed max-w-2xl">
                                        {cap.description}
                                    </p>
                                </div>
                            </div>
                        </motion.div>
                    ))}
                </div>
            </div>
        </section>
    )
}
