"use client"

import { motion } from "framer-motion"

export function ExperienceSection() {
    return (
        <section className="py-24 px-6 md:px-12 lg:px-24 relative">
            <div className="max-w-7xl mx-auto">
                <div className="grid grid-cols-1 md:grid-cols-2 gap-12 md:gap-24">
                    <motion.div
                        initial={{ opacity: 0, y: 20 }}
                        whileInView={{ opacity: 1, y: 0 }}
                        viewport={{ once: true }}
                        transition={{ duration: 0.6 }}
                    >
                        <span className="text-label-sm text-on-surface-variant tracking-[0.3em]">
                            EXPERIENCE
                        </span>
                        <div className="mt-6 space-y-6">
                            <div className="bg-surface-container p-6 border border-yellow-500/20">
                                <p className="text-label-sm text-yellow-500/80">
                                    Desperately finding one
                                </p>
                            </div>
                        </div>
                    </motion.div>

                    <motion.div
                        initial={{ opacity: 0, y: 20 }}
                        whileInView={{ opacity: 1, y: 0 }}
                        viewport={{ once: true }}
                        transition={{ duration: 0.6, delay: 0.15 }}
                    >
                        <span className="text-label-sm text-on-surface-variant tracking-[0.3em]">
                            EDUCATION
                        </span>
                        <div className="mt-6 bg-surface-container p-6">
                            <h3 className="text-headline-sm text-on-surface">
                                B.Tech Computer Science and Engineering
                            </h3>
                            <p className="text-body-md text-on-surface-variant mt-2">
                                Vellore Institute of Technology · 2022 - 2026
                            </p>
                        </div>
                    </motion.div>
                </div>
            </div>
        </section>
    )
}
