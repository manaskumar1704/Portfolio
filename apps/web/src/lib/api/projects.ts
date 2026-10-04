import type { Project } from "./types";

const PROJECTS: Project[] = [
  {
    name: "AgentFlow",
    status: "completed",
    label: "completed",
    meta: "12 files · +842 −133",
    desc: "Multi-agent orchestration framework that routes tasks across specialized LLM workers with shared memory.",
    stack: "Python · LangGraph · Redis · FastAPI",
  },
  {
    name: "GraphSAGE Fraud Detection",
    status: "completed",
    label: "completed",
    meta: "8 files · +510 −97",
    desc: "Graph neural network that flags fraudulent transactions from the transaction graph in near real time.",
    stack: "PyTorch Geometric · FastAPI · Postgres",
  },
  {
    name: "MCP Job-Tools Server",
    status: "completed",
    label: "completed",
    meta: "9 files · +388 −64",
    desc: "Model Context Protocol server exposing job-search tools (search, filter, tailor) to any MCP client.",
    stack: "TypeScript · MCP SDK · Node",
  },
  {
    name: "GenAI Career Tracker",
    status: "running",
    label: "running",
    meta: "in progress · +221 −40",
    desc: "LLM-assisted tracker that parses job posts, scores fit, and drafts tailored application copy.",
    stack: "Next.js · OpenAI · SQLite",
  },
  {
    name: "AI Portfolio Chat",
    status: "soon",
    label: "coming soon",
    meta: "planned",
    desc: "A RAG chatbot that answers questions about this portfolio — grounded in the résumé and project docs.",
    stack: "RAG · Embeddings · Vector DB",
  },
];

/** Mock shapes match GET /projects on the FastAPI backend. */
export async function listProjects(): Promise<Project[]> {
  return PROJECTS;
}
