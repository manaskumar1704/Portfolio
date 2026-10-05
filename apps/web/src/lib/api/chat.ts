import type { ChatReply } from "./types";
import { RESUME } from "./fs";

const REPLIES: { keywords: string[]; reply: string }[] = [
  {
    keywords: ["project", "work", "built", "build", "portfolio", "app"],
    reply:
      "Here's what Manas has been building:\n\n" +
      "▸ AgentFlow — multi-agent orchestration framework (✔ completed)\n" +
      "▸ GraphSAGE Fraud Detection — graph net for transaction fraud (✔ completed)\n" +
      "▸ MCP Job-Tools Server — job-search tools for MCP clients (✔ completed)\n" +
      "▸ GenAI Career Tracker — LLM-assisted application tracker (◐ running)\n" +
      "▸ AI Portfolio Chat — RAG chatbot over this portfolio (◌ coming soon)\n\n" +
      "Scroll down for the full task cards.",
  },
  {
    keywords: [
      "resume",
      "cv",
      "experience",
      "background",
      "career",
      "role",
      "job",
    ],
    reply:
      RESUME + "\n\nFor the full CV, email him — see `contact.md`.",
  },
  {
    keywords: [
      "contact",
      "email",
      "reach",
      "hire",
      "available",
      "linkedin",
      "github",
    ],
    reply:
      "Easiest ways to reach Manas:\n\n" +
      "email     manas@example.com\n" +
      "github    github.com/manas-dev\n" +
      "linkedin  linkedin.com/in/manas-dev\n\n" +
      "He's open to GenAI / full-stack roles. (Placeholder links — swap in the real handles.)",
  },
  {
    keywords: ["skill", "stack", "tech", "tools", "language", "framework"],
    reply:
      "Stack, by area:\n\n" +
      "languages  Python · TypeScript · Go · SQL · Bash\n" +
      "genai/llm  RAG · LangChain · LlamaIndex · agents · evals · pgvector\n" +
      "frontend   React · Next.js · Tailwind · Framer Motion\n" +
      "backend    FastAPI · Node.js · Postgres · Redis · Kafka\n" +
      "infra      Docker · Kubernetes · AWS · Terraform · CI/CD",
  },
  {
    keywords: ["about", "who", "yourself", "manas", "summary"],
    reply:
      "Manas builds products where language models meet real software — retrieval that cites its sources, agents that stay in their lane, and interfaces that make the result legible. He works end to end: prompt and schema on one side, the button a person presses on the other.",
  },
  {
    keywords: ["hello", "hi", "hey", "yo"],
    reply:
      "Hey — I'm Manas's agent. Ask me about his projects, resume, skills, or how to reach him. The buttons below are a good place to start.",
  },
];

const FALLBACK =
  "This is a scripted demo of Manas's agent, so I only cover a few topics. Try asking about his projects, resume, skills, or how to contact him.";

export const GREETING =
  "Hi — I'm Manas's agent. Ask me anything in plain language: his projects, resume, skills, or how to reach him.";

/** Mock shape matches POST /chat on the FastAPI backend. */
export async function ask(text: string): Promise<ChatReply> {
  const lower = text.toLowerCase();
  const match = REPLIES.find((entry) =>
    entry.keywords.some((keyword) => lower.includes(keyword)),
  );
  return { reply: match ? match.reply : FALLBACK };
}
