"use client"

import { GlassCard } from "../ui/GlassCard"
import { Layout, Server, Terminal, Cpu } from "lucide-react"

const skills = [
    {
        category: "Frontend Architecture",
        icon: <Layout className="w-6 h-6" />,
        items: ["React", "Next.js 14", "TypeScript", "Tailwind CSS", "Framer Motion", "Three.js"]
    },
    {
        category: "Backend Systems",
        icon: <Server className="w-6 h-6" />,
        items: ["Node.js", "Python", "PostgreSQL", "GraphQL", "Redis", "Docker"]
    },
    {
        category: "DevOps & Tools",
        icon: <Terminal className="w-6 h-6" />,
        items: ["Git", "AWS", "CI/CD Pipelines", "Linux", "Vercel", "Jest"]
    },
    {
        category: "AI & Emerging Tech",
        icon: <Cpu className="w-6 h-6" />,
        items: ["OpenAI API", "LangChain", "Vector DBs", "Model Fine-tuning"]
    }
]

export function SkillsSection() {
    return (
        <section className="py-24 px-4 relative">
            <div className="max-w-6xl mx-auto">
                <h2 className="text-3xl md:text-4xl font-serif text-center mb-16 text-white">
                    <span className="text-reiatsu">{"///"}</span> Technical Arsenal
                </h2>

                <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                    {skills.map((skill, index) => (
                        <GlassCard
                            key={index}
                            intensity="low"
                            className="p-8 group hover:border-reiatsu/30 flex flex-col gap-6"
                        >
                            <div className="flex items-center gap-4 mb-2">
                                <div className="p-3 rounded-lg bg-white/5 text-gray-400 group-hover:text-reiatsu group-hover:bg-reiatsu/10 transition-colors duration-300">
                                    {skill.icon}
                                </div>
                                <h3 className="text-xl font-serif text-gray-200 group-hover:text-white transition-colors">
                                    {skill.category}
                                </h3>
                            </div>

                            <div className="flex flex-wrap gap-2">
                                {skill.items.map((item, i) => (
                                    <span
                                        key={i}
                                        className="px-3 py-1 text-xs font-mono text-gray-400 border border-white/5 rounded-full bg-white/[0.02] group-hover:border-reiatsu/20 group-hover:text-gray-300 transition-colors duration-300"
                                    >
                                        {item}
                                    </span>
                                ))}
                            </div>
                        </GlassCard>
                    ))}
                </div>
            </div>
        </section>
    )
}
