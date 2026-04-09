"use client"

import { useState, useCallback } from "react"
import { motion } from "framer-motion"
import { ArrowRight } from "lucide-react"
import { cn } from "@/lib/utils"
import Image from "next/image"

const projects = [
    {
        slot: "A",
        number: "01",
        badge: "GenAI",
        year: "2026",
        title: "RAG INTELLIGENCE PLATFORM",
        description: "End-to-end production RAG system with hybrid search (vector + BM25), multi-hop reasoning chains, PII redaction via Presidio, Cohere reranking, and a RAGAS evaluation suite. Async FastAPI backend with real-time LangSmith observability.",
        tech: ["LangGraph", "FastAPI", "pgvector", "Cohere", "RAGAS", "LangSmith", "Groq API", "Docker"],
        github: "https://github.com/manaskumar1704/rag-intelligence-platform",
        live: "https://rag-demo.vercel.app",
        image: "/images/projects/project-rag.png"
    },
    {
        slot: "B",
        number: "02",
        badge: "Agentic AI",
        year: "2026",
        title: "NL → N8N WORKFLOW AGENT",
        description: "Natural language to automation. Parses intent, generates valid n8n workflow JSON via multi-step tool-calling. Validates node connections and deploys live via the n8n API.",
        tech: ["LangGraph", "Groq API", "n8n API", "FastAPI", "Next.js"],
        github: "https://github.com/manaskumar1704/nl-n8n-agent",
        live: "https://nl-workflow.vercel.app",
        image: "/images/projects/project-n8n.png"
    },
    {
        slot: "C",
        number: "03",
        badge: "Autonomous System",
        isFullWidth: true,
        year: "2026",
        title: "GEOPOLITICAL CRISIS MONITOR",
        description: "Autonomous multi-agent system monitoring geopolitical events in real-time across news APIs, RSS, and social signals. LangGraph-orchestrated parallel agents for scraping, summarization, and risk-scoring. Delivers structured briefings with source attribution and confidence scores.",
        tech: ["LangGraph", "APScheduler", "Groq API", "Supabase", "Docker", "GitHub Actions"],
        github: "https://github.com/manaskumar1704/geopolitical-crisis-monitor",
        live: "https://geo-monitor.vercel.app",
        image: "/images/projects/project-geo.png"
    },
    {
        slot: "D",
        number: "04",
        badge: "Multi-Agent",
        year: "2026",
        title: "FINANCIAL RESEARCH ASSISTANT",
        description: "Collaborative multi-agent system for financial research. Specialized agents handle SEC filing parsing, earnings call sentiment via FinBERT, web search for market context, and report synthesis. Human-in-the-loop checkpoints via LangGraph. AWS Bedrock model fallback.",
        tech: ["LangGraph", "FinBERT", "AWS Bedrock", "Groq API", "FastAPI", "shadcn/ui"],
        github: "https://github.com/manaskumar1704/multi-agent-finresearch",
        live: "https://fin-research.vercel.app",
        image: "/images/projects/project_finai.png"
    },
    {
        slot: "E",
        number: "05",
        badge: "ML Research",
        year: "2025",
        title: "GRAPHSAGE FRAUD DETECTION",
        description: "Graph neural network fraud detection trained on transaction graphs. GraphSAGE node classification identifies anomalous patterns with high precision across high-volume financial datasets. Strongest academic ML result.",
        tech: ["PyTorch", "GraphSAGE", "scikit-learn", "Pandas", "Python"],
        github: "https://github.com/manaskumar1704/graphsage-fraud",
        live: null,
        image: "/images/projects/project_graphsage.png"
    }
]

export function ProjectsSection() {
    const [imageErrors, setImageErrors] = useState<Record<number, boolean>>({})

    const handleImageError = useCallback((index: number) => {
        setImageErrors(prev => ({ ...prev, [index]: true }))
    }, [])

    return (
        <section id="projects" className="py-24 px-6 md:px-12 lg:px-24 relative bg-surface-container-low">
            <div className="max-w-7xl mx-auto">
                <div className="flex flex-col md:flex-row md:items-end md:justify-between mb-16">
                    <div>
                        <span className="text-label-sm text-on-surface-variant tracking-[0.3em]">
                            SELECTED WORKS
                        </span>
                        <h2 className="font-display text-6xl md:text-7xl lg:text-8xl leading-[0.95] tracking-[-0.04em] uppercase text-on-surface mt-4">
                            PROJECTS.
                        </h2>
                    </div>
                </div>

                <div className="grid grid-cols-12 gap-6">
                    {projects.map((project, index) => (
                        <motion.div
                            key={index}
                            initial={{ opacity: 0, y: 20 }}
                            whileInView={{ opacity: 1, y: 0 }}
                            viewport={{ once: true }}
                            transition={{ duration: 0.6, delay: index * 0.1 }}
                            className={cn(
                                "group relative overflow-hidden",
                                project.slot === "A" && "md:col-span-8",
                                project.slot === "B" && "md:col-span-4 md:mt-32",
                                project.slot === "C" && "md:col-span-12",
                                (project.slot === "D" || project.slot === "E") && "md:col-span-6"
                            )}
                        >
                            <div className="flex flex-col h-full bg-surface-container border border-surface-container-high">
                                <div className="relative overflow-hidden bg-surface">
                                    {imageErrors[index] ? (
                                        <div className="w-full aspect-[16/10] bg-surface-container-high flex items-center justify-center">
                                            <span className="text-on-surface-variant text-sm">Image unavailable</span>
                                        </div>
                                    ) : (
                                        <Image
                                            src={project.image}
                                            alt={project.title}
                                            fill
                                            onError={() => handleImageError(index)}
                                            className="object-cover grayscale opacity-80 group-hover:grayscale-0 group-hover:scale-105 group-hover:opacity-100 transition-all duration-700"
                                        />
                                    )}
                                </div>

                                <div className="flex-1 p-4 md:p-6">
                                    <div className="flex items-center justify-between mb-4">
                                        <div className="flex items-center gap-3">
                                            <span className="text-label-sm text-on-surface-variant/60">{project.number}</span>
                                            {(project.badge || project.isFullWidth) && (
                                                <span className="text-label-xs text-primary px-2 py-0.5 bg-primary/10 rounded">
                                                    {project.badge}
                                                </span>
                                            )}
                                        </div>
                                        {!project.isFullWidth && project.year && (
                                            <span className="text-label-sm text-on-surface-variant/60">
                                                {project.year}
                                            </span>
                                        )}
                                    </div>

                                    <h3 className={cn(
                                        "font-display uppercase tracking-tighter text-on-surface group-hover:italic transition-all duration-300",
                                        project.slot === "C" ? "text-5xl md:text-7xl" : "text-2xl md:text-3xl"
                                    )}>
                                        {project.title}
                                    </h3>
                                    <p className="text-body-md text-on-surface-variant mt-3 max-w-xl line-clamp-2">
                                        {project.description}
                                    </p>
                                    <div className="flex flex-wrap gap-2 mt-4">
                                        {project.tech.map((tech, i) => (
                                            <span key={i} className="text-label-xs text-on-surface-variant/70">
                                                {tech}
                                            </span>
                                        ))}
                                    </div>
                                    <div className="flex items-center gap-4 mt-4">
                                        <a
                                            href={project.github}
                                            target="_blank"
                                            rel="noopener noreferrer"
                                            className="text-label-sm text-primary hover:text-primary/80 transition-colors"
                                        >
                                            GitHub →
                                        </a>
                                        {project.live && (
                                            <a
                                                href={project.live}
                                                target="_blank"
                                                rel="noopener noreferrer"
                                                className="group/cta text-label-sm text-on-surface-variant hover:text-on-surface transition-colors flex items-center gap-1"
                                            >
                                                View Case 
                                                <ArrowRight className="w-3 h-3 transition-transform duration-300 group-hover/cta:translate-x-1" />
                                            </a>
                                        )}
                                    </div>
                                </div>
                            </div>
                        </motion.div>
                    ))}
                </div>
            </div>
        </section>
    )
}
