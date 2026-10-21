# Manas Kumar — AI Engineer, Backend & Full-Stack Developer

## Candidate Overview & Location
- **Name:** Manas Kumar
- **Education:** B.Tech in Computer Science and Engineering (Graduated 2026)
- **Location:** Pune, Maharashtra, India (Available immediately for roles in Kharadi, Magarpatta City, SP Infocity, Hinjewadi, and remote/hybrid setups).
- **Target Roles:** AI Engineer, GenAI Engineer, Backend Software Engineer (Python), Full-Stack Developer.

## Core Technical Stack
- **Languages:** Python (3.12+, Asyncio, Type Hints), TypeScript, SQL, Bash.
- **Backend & APIs:** FastAPI, Django, SQLAlchemy 2.0 (Async), Pydantic v2, Alembic, REST, Server-Sent Events (SSE), WebSockets, Streamable HTTP Model Context Protocol (MCP), Celery.
- **Databases & Caching:** PostgreSQL, Supabase, pgvector (HNSW & IVFFlat indexing), Full-Text Search (tsvector / BM25), Upstash Redis, SQLite.
- **AI, RAG & Machine Learning:** Google Gemini API (Structured Outputs / response_schema), Hybrid GraphRAG (Reciprocal Rank Fusion, Vector + Lexical + Knowledge Graph), GLiNER (Zero-Shot NER), UMAP dimensionality reduction, NetworkX, XGBoost, prompt injection guardrails.
- **Frontend & Visualization:** Next.js (App Router), React, React Three Fiber (R3F / Three.js 3D visualizations), Tailwind CSS, Shadcn UI, Zustand.
- **DevOps, Security & Tooling:** Docker, uv package manager, pytest, Git, Linux/macOS/Windows terminal workflows, SHA-256 scoped API keys, MultiFernet key rotation encryption, SlowAPI rate limiting, Tree-sitter AST static analysis, Typst PDF compilation.

## Engineering Philosophy
1. **Deterministic First, LLM Second:** Never use a probabilistic LLM for work that deterministic SQL, vector math, AST parsing, or compiled typesetting can do faster and with 100% reliability.
2. **Zero-Dependency Thin Adapters:** Prefer lightweight, transparent async clients (`httpx`, raw SQL/CTE pipelines, Pydantic schemas) over bloated framework abstractions that obscure latency and failure modes.
3. **Production Security by Default:** Every public-facing AI endpoint is protected by CIDR-aware IP hashing, Redis rate limiting, strict Pydantic input validation, encrypted BYOK support (MultiFernet), and human-in-the-loop approval gates for external side effects (such as sending emails).
