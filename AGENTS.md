# Agents & Tech Stack Lock

Project: chat-first AI portfolio. Spec: `.docs/INITIAL_BUILD_PROMPT.md`.

## 🔒 Locked Tech Stack

**Do NOT introduce new libraries without explicit user approval.** Add it to
`docs/decisions/` first with a one-paragraph justification.

| Layer | Choice |
|---|---|
| Frontend | Next.js (App Router), shadcn/ui, Tailwind, Bun, Vercel |
| API | FastAPI, managed with uv, Docker, Render free web service |
| Database | Neon Postgres + pgvector. **Not** Render Postgres (expires in 30 days) |
| LLM (app runtime) | Claude API, `claude-haiku-4-5-20251001` |
| Embeddings | Small local model (fastembed) — must fit 512 MB RAM |
| Evals | pytest runner in `evals/` |
| Tracing | Langfuse |
| Email | Resend |
| MCP | Official Python MCP SDK |
| CI | GitHub Actions |

No LangChain. Native Claude tool-use API. Tool-calling is the spine; RAG is one
tool; MCP is a separate showcase layer that **imports** from `apps/api`, never copies.

## 📁 Layout

```
apps/web     Next.js frontend
apps/api     FastAPI backend (routers/ services/ tools/ core/)
corpus/      Markdown source of truth for RAG
evals/       Golden set + runner
mcp/         MCP server (imports from apps/api tools)
docs/        AI_USAGE.md, decisions/ ADRs
graphify-out/ Generated graph — git-ignored, never edit
```

## 🐴 ponytail scope rule (important)

Ponytail governs **how** to implement, **not what** to build. The showcase
deliverables in the spec — RAG, tool-calling, MCP server, evals, tracing, CI — are
**required**, not bloat.

- If ponytail's "use the simplest thing" ladder conflicts with a required
  component: **keep the component**, keep the implementation minimal, and record
  the tension in `docs/decisions/`.
- Any deferred shortcut gets a `ponytail:` comment naming the upgrade path.

Useful commands: `/ponytail [lite|full|ultra|off]`, `/ponytail-review`,
`/ponytail-audit`, `/ponytail-debt`.

## 🕸️ graphify usage

Query the graph before grepping:

```
graphify query "how does the chat tool loop work?"
graphify path "search_portfolio" "send_message"
graphify explain "IngestionService"
graphify update .    # re-run after structural changes (code only, no LLM)
```

This repo is small. graphify is a **workflow experiment, not a necessity** — say
so honestly in `docs/AI_USAGE.md`.

## 🛠️ Standards

- Python: type hints on every function, small single-purpose modules, no
  duplicated logic, tests for every tool.
- TypeScript: functional components with typed props, Tailwind utility classes
  (no inline styles / CSS modules).
- Never commit secrets. `.env` is git-ignored; ship `.env.example`.
- Free tiers only. Add `/health` that does **not** touch the DB (Neon must be
  able to scale to zero).
- Remove unused imports, variables, and `console.log` before committing.
- **Do not guess.** Batch questions to the user; do not ask one at a time.
- Verify third-party facts (free-tier limits, package names, CLI flags) against
  official docs or `--help` before relying on them.
