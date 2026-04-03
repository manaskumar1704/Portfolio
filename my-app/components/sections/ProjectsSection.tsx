"use client"

import { motion } from "framer-motion"
import { ArrowRight } from "lucide-react"

const projects = [
    {
        title: "NEURAL ENGINE v2",
        description: "Real-time distributed computation for edge-AI rendering.",
        tags: ["SYSTEMS", "RUST"],
        year: "2024",
        role: "LEAD ENGINEER"
    },
    {
        title: "LUMINA UI",
        description: "A spatial component library for next-gen headsets.",
        tags: ["WEBGL", "REACT"],
        year: "2024",
        role: "ARCHITECT"
    },
    {
        title: "CORE PROTOCOL",
        description: "Ultra-low latency communication framework.",
        tags: ["GO", "GRPC"],
        year: "2023",
        role: "SYSTEMS DESIGN"
    },
    {
        title: "ZENITH OPERATING OS",
        description: "An experimental interface for kernel-level interaction.",
        tags: ["RUST", "KERNEL"],
        year: "2023",
        role: "CREATIVE TECH"
    }
]

export function ProjectsSection() {
    return (
        <section id="works" className="py-24 px-6 md:px-12 lg:px-24 relative bg-surface-container-low">
            <div className="max-w-7xl mx-auto">
                <div className="flex flex-col md:flex-row md:items-end md:justify-between mb-16">
                    <h2 className="text-headline-lg text-on-surface">
                        SELECTED WORKS
                    </h2>
                    <span className="text-label-sm text-on-surface-variant mt-2 md:mt-0">
                        [001—004] ARCHIVE/2024
                    </span>
                </div>

                {/* Asymmetrical grid layout */}
                <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                    {/* Large featured project - spans 2 cols on md */}
                    <motion.div
                        initial={{ opacity: 0, y: 20 }}
                        whileInView={{ opacity: 1, y: 0 }}
                        viewport={{ once: true }}
                        transition={{ duration: 0.6 }}
                        className="md:col-span-2 group"
                    >
                        <div className="bg-surface-container p-8 md:p-12 transition-all duration-500 hover:bg-surface-container-high">
                            <div className="flex flex-col md:flex-row md:items-end md:justify-between gap-6">
                                <div className="flex-1">
                                    <div className="flex items-center gap-3 mb-4">
                                        {projects[0].tags.map((tag, i) => (
                                            <span key={i} className="text-label-sm text-on-surface-variant/60">
                                                {tag}
                                            </span>
                                        ))}
                                    </div>
                                    <h3 className="text-headline-md text-on-surface group-hover:text-primary transition-colors duration-300">
                                        {projects[0].title}
                                    </h3>
                                    <p className="text-body-md text-on-surface-variant mt-3 max-w-lg">
                                        {projects[0].description}
                                    </p>
                                </div>
                                <div className="flex items-center gap-2 text-label-sm text-primary/70 group-hover:text-primary transition-colors cursor-pointer">
                                    VIEW CASE STUDY
                                    <ArrowRight className="w-3 h-3" />
                                </div>
                            </div>
                        </div>
                    </motion.div>

                    {/* Smaller projects */}
                    {projects.slice(1).map((project, index) => (
                        <motion.div
                            key={index}
                            initial={{ opacity: 0, y: 20 }}
                            whileInView={{ opacity: 1, y: 0 }}
                            viewport={{ once: true }}
                            transition={{ duration: 0.5, delay: index * 0.1 }}
                            className="group"
                        >
                            <div className="bg-surface-container p-8 transition-all duration-500 hover:bg-surface-container-high h-full flex flex-col justify-between">
                                <div>
                                    <div className="flex items-start justify-between mb-6">
                                        <span className="text-label-sm text-on-surface-variant/40">
                                            {project.year}
                                        </span>
                                        <span className="text-label-sm text-on-surface-variant/40">
                                            {project.role}
                                        </span>
                                    </div>
                                    <h3 className="text-headline-sm text-on-surface group-hover:text-primary transition-colors duration-300">
                                        {project.title}
                                    </h3>
                                    <p className="text-body-md text-on-surface-variant mt-3">
                                        {project.description}
                                    </p>
                                </div>
                                <div className="flex items-center gap-3 mt-6">
                                    {project.tags.map((tag, i) => (
                                        <span key={i} className="text-label-sm text-on-surface-variant/60">
                                            {tag}
                                        </span>
                                    ))}
                                </div>
                            </div>
                        </motion.div>
                    ))}
                </div>
            </div>
        </section>
    )
}
