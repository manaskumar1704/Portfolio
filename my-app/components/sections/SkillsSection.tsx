"use client"

import { motion } from "framer-motion"
import { Chip } from "../ui/Chip"

const skills = [
    {
        category: "Frontend Architecture",
        items: ["React", "Next.js 14", "TypeScript", "Tailwind CSS", "Framer Motion", "Three.js"]
    },
    {
        category: "Backend Systems",
        items: ["Node.js", "Python", "PostgreSQL", "GraphQL", "Redis", "Docker"]
    },
    {
        category: "DevOps & Tools",
        items: ["Git", "AWS", "CI/CD Pipelines", "Linux", "Vercel", "Jest"]
    },
    {
        category: "AI & Emerging Tech",
        items: ["OpenAI API", "LangChain", "Vector DBs", "Model Fine-tuning"]
    }
]

export function SkillsSection() {
    return (
        <section className="py-24 px-6 md:px-12 lg:px-24 relative">
            <div className="max-w-7xl mx-auto">
                <div className="flex flex-col md:flex-row md:items-end md:justify-between mb-16">
                    <h2 className="text-headline-lg text-on-surface">
                        THE STACK
                    </h2>
                    <span className="text-label-sm text-on-surface-variant mt-2 md:mt-0">
                        TECHNOLOGICAL PROFICIENCY INDEX
                    </span>
                </div>

                <div className="flex flex-wrap gap-3">
                    {skills.flatMap((skill, skillIndex) =>
                        skill.items.map((item, itemIndex) => (
                            <motion.div
                                key={`${skillIndex}-${itemIndex}`}
                                initial={{ opacity: 0, y: 12 }}
                                whileInView={{ opacity: 1, y: 0 }}
                                viewport={{ once: true }}
                                transition={{
                                    duration: 0.4,
                                    delay: (skillIndex * skill.items.length + itemIndex) * 0.03,
                                    ease: "easeOut"
                                }}
                            >
                                <Chip label={item} />
                            </motion.div>
                        ))
                    )}
                </div>

                {/* Category breakdown */}
                <div className="mt-16 grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-8">
                    {skills.map((skill, index) => (
                        <motion.div
                            key={index}
                            initial={{ opacity: 0, y: 16 }}
                            whileInView={{ opacity: 1, y: 0 }}
                            viewport={{ once: true }}
                            transition={{ duration: 0.5, delay: index * 0.1 }}
                            className="bg-surface-container p-6"
                        >
                            <span className="text-label-sm text-on-surface-variant/60">
                                {String(index + 1).padStart(2, "0")}
                            </span>
                            <h3 className="text-headline-sm text-on-surface mt-2 mb-3">
                                {skill.category}
                            </h3>
                            <div className="flex flex-wrap gap-2">
                                {skill.items.map((item, i) => (
                                    <span
                                        key={i}
                                        className="text-label-sm text-primary/70"
                                    >
                                        {item}
                                    </span>
                                ))}
                            </div>
                        </motion.div>
                    ))}
                </div>
            </div>
        </section>
    )
}
