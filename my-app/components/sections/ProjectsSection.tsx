"use client"

import { GlassCard } from "../ui/GlassCard"
import { ExternalLink, Github } from "lucide-react"

const projects = [
    {
        title: "Project Aizen",
        description: "An immersive developer portfolio pushing the boundaries of web aesthetics. Built with Next.js 14, Framer Motion, and Tailwind CSS. Features deep glassmorphism and custom design tokens.",
        tags: ["Next.js", "React", "TypeScript", "Tailwind"],
        image: "/project-1.jpg", // Placeholder
        demoLink: "#",
        codeLink: "#"
    },
    {
        title: "Ether Sanctum",
        description: "A decentralized voting application built on Ethereum. Ensuring transparency and immutability through smart contracts. Audited and optimized for gas efficiency.",
        tags: ["Solidity", "Hardhat", "Ethers.js", "React"],
        image: "/project-2.jpg",
        demoLink: "#",
        codeLink: "#"
    },
    {
        title: "Neural Nexus",
        description: "AI-powered data visualization dashboard. Processes real-time data streams and renders complex graphs using WebGL. High performance for large datasets.",
        tags: ["Python", "TensorFlow", "WebGL", "Three.js"],
        image: "/project-3.jpg",
        demoLink: "#",
        codeLink: "#"
    }
]

export function ProjectsSection() {
    return (
        <section id="projects" className="py-24 px-4 relative bg-black/20">
            <div className="max-w-7xl mx-auto">
                <h2 className="text-3xl md:text-4xl font-serif text-center mb-4 text-white">
                    <span className="text-reiatsu">{"///"}</span> Constructed Realities
                </h2>
                <p className="text-center text-muted-foreground font-mono mb-16 max-w-2xl mx-auto">
                    Selected works demonstrating mastery over the digital medium.
                </p>

                <div className="grid grid-cols-1 gap-12">
                    {projects.map((project, index) => (
                        <GlassCard
                            key={index}
                            intensity="medium"
                            className="group flex flex-col md:flex-row overflow-hidden min-h-[400px]"
                        >
                            {/* Image Size / Container */}
                            <div className="md:w-3/5 h-64 md:h-auto relative overflow-hidden bg-obsidian">
                                <div className="absolute inset-0 bg-gradient-to-t from-obsidian to-transparent opacity-60 z-10" />
                                {/* Placeholder for actual image - using a colored div for now for effect */}
                                <div className={`w-full h-full bg-gradient-to-br from-gray-900 to-gray-800 group-hover:scale-105 transition-transform duration-700 ease-out`} />

                                {/* Overlay Text on Image */}
                                <div className="absolute bottom-0 left-0 p-8 z-20 md:hidden">
                                    <h3 className="text-2xl font-serif font-bold text-white mb-2">{project.title}</h3>
                                </div>
                            </div>

                            {/* Content Side */}
                            <div className="md:w-2/5 p-8 md:p-12 flex flex-col justify-center relative bg-white/[0.01]">
                                <div className="hidden md:block">
                                    <h3 className="text-3xl font-serif font-bold text-white mb-6 group-hover:text-reiatsu transition-colors duration-300">
                                        {project.title}
                                    </h3>
                                </div>

                                <p className="text-gray-400 font-sans leading-relaxed mb-8">
                                    {project.description}
                                </p>

                                <div className="flex flex-wrap gap-2 mb-10">
                                    {project.tags.map((tag, i) => (
                                        <span key={i} className="text-xs font-mono text-hogyoku px-2 py-1 border border-hogyoku/20 rounded bg-hogyoku/5">
                                            {tag}
                                        </span>
                                    ))}
                                </div>

                                <div className="flex items-center gap-6 mt-auto">
                                    <a
                                        href={project.demoLink}
                                        className="flex items-center gap-2 text-sm font-bold tracking-widest text-white uppercase hover:text-reiatsu transition-colors"
                                    >
                                        Live Demo <ExternalLink className="w-4 h-4" />
                                    </a>
                                    <a
                                        href={project.codeLink}
                                        className="flex items-center gap-2 text-sm font-bold tracking-widest text-gray-500 uppercase hover:text-white transition-colors"
                                    >
                                        Source Code <Github className="w-4 h-4" />
                                    </a>
                                </div>
                            </div>
                        </GlassCard>
                    ))}
                </div>
            </div>
        </section>
    )
}
