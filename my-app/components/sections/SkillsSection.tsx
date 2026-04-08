"use client"

import { motion } from "framer-motion"

const skillCategories = [
    {
        category: "AI / LLM Core",
        items: ["LangGraph", "LangChain", "Anthropic Claude API", "AWS Bedrock", "OpenAI API", "LlamaIndex", "Hugging Face", "FinBERT", "Guardrails AI", "Presidio", "RAGAS", "LangSmith"]
    },
    {
        category: "Vector & Retrieval",
        items: ["pgvector", "Supabase", "Pinecone", "ChromaDB", "Cohere Rerank"]
    },
    {
        category: "Backend",
        items: ["Python 3.11", "FastAPI (async)", "Node.js", "REST", "WebSockets", "APScheduler"]
    },
    {
        category: "Frontend",
        items: ["Next.js 14", "React", "TypeScript", "Tailwind CSS", "shadcn/ui"]
    },
    {
        category: "DevOps & Infra",
        items: ["Docker", "GitHub Actions", "Vercel", "AWS (Bedrock + S3)", "uv"]
    },
    {
        category: "ML / Research",
        items: ["PyTorch", "GraphSAGE", "scikit-learn", "XGBoost", "CNNs", "Pandas", "NumPy"]
    },
    {
        category: "Databases",
        items: ["PostgreSQL", "Supabase", "Redis", "MongoDB"]
    }
]

export function SkillsSection() {
    return (
        <section id="skills" className="py-24 px-6 md:px-12 lg:px-24 relative">
            <div className="max-w-7xl mx-auto">
                <div className="flex flex-col md:flex-row md:items-end md:justify-between mb-16">
                    <div>
                        <span className="text-label-sm text-on-surface-variant tracking-[0.3em]">
                            TECHNICAL STACK
                        </span>
                        <h2 className="font-display text-4xl md:text-5xl lg:text-6xl leading-[0.95] tracking-[-0.04em] uppercase text-on-surface mt-4">
                            TOOLS & SYSTEMS.
                        </h2>
                    </div>
                </div>

                <div className="space-y-8">
                    {skillCategories.map((category, catIndex) => (
                        <motion.div
                            key={catIndex}
                            initial={{ opacity: 0, y: 16 }}
                            whileInView={{ opacity: 1, y: 0 }}
                            viewport={{ once: true }}
                            transition={{ duration: 0.5, delay: catIndex * 0.05 }}
                        >
                            <h3 className="text-label-sm text-primary mb-3 tracking-wider">
                                {category.category}
                            </h3>
                            <div className="flex flex-wrap gap-2">
                                {category.items.map((item, itemIndex) => (
                                    <span
                                        key={itemIndex}
                                        className="bg-surface-container-highest text-on-surface-variant px-3 py-1 text-xs font-display uppercase tracking-tighter transition-colors duration-200 hover:bg-primary/10 hover:text-primary cursor-default"
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
