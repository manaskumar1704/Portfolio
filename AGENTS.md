# Agents & Tech Stack Lock

Project: chat-first AI portfolio. Spec: `.docs/INITIAL_BUILD_PROMPT.md`.

## 🔒 Locked Tech Stack

**Do NOT introduce new libraries without explicit user approval.** Add it to
`docs/decisions/` first with a one-paragraph justification.

| Layer | Choice |
|---|---|
| Frontend | Next.js (App Router), shadcn/ui, Tailwind, Bun, Vercel |
| UI vibe | Terminal / Claude Code-like, monospace-forward |
| API | FastAPI, managed with uv, Docker, Render free web service |
| Database | Neon Postgres + pgvector. **Not** Render Postgres (expires in 30 days) |
| LLM (app runtime) | Claude API, `claude-haiku-4-5-20251001` |
| Embeddings | Small local model (fastembed), must fit 512 MB RAM |
| Evals | pytest runner in `evals/` |
| Tracing | Langfuse |
| Email | Resend |
| MCP | Official Python MCP SDK |
| CI | GitHub Actions |

No LangChain. Native Claude tool-use API. Tool-calling is the spine; RAG is one
tool; MCP is a separate showcase layer that **imports** from `apps/api`, never copies.

## 🎨 Frontend

Work only in `apps/web`. Do not touch `apps/api`, `mcp/`, or Neon until told.
Backend items elsewhere in this file are context only.

- **Design reference:** `design/` holds the Open Design export (HTML/CSS and
  screenshots per screen). Match the look and structure; do not copy its markup.
- **Plan first:** read `design/`, then write `docs/frontend-plan.md` containing
  the design tokens, a component inventory (primitives vs feature components),
  and the route list. Build nothing until I have reviewed it.
- **Build in slices:** tokens + layout shell → shared primitives → one page at
  a time. One slice per prompt.
- **Mocked data:** all data goes through `apps/web/src/lib/api/` using typed
  fixtures (chat stream, GitHub repos, contact). Mock shapes must match what
  the real API will return, so swapping in the backend only changes that folder.
- **UI skills:** for any UI work use the frontend-design skill (and taste-skill
  if installed).
- **Verify every slice:** use the playwright-cli skill to screenshot at desktop
  and mobile widths, compare against `design/`, and fix gaps before moving on.
- **Commit after each slice.**
- **Neon/Postgres skills:** ignore for now.

## 📁 Layout

```
apps/web     Next.js frontend
  src/components/ui    dumb, reusable primitives (shadcn-based)
  src/features/<name>  feature components + hooks
  src/lib/api          data access layer (mocked for now)
  src/styles           tokens: colors, spacing, type
apps/api     FastAPI backend (routers/ services/ tools/ core/)
design/      Open Design export, reference only
corpus/      Markdown source of truth for RAG
evals/       Golden set + runner
mcp/         MCP server (imports from apps/api tools)
docs/        AI_USAGE.md, decisions/ ADRs, frontend-plan.md
graphify-out/ Generated graph, git-ignored, never edit
```

## 🐴 ponytail scope rule (important)

Ponytail governs **how** to implement, **not what** to build. The showcase
deliverables in the spec (RAG, tool-calling, MCP server, evals, tracing, CI) are
**required**, not bloat.

- If ponytail's "use the simplest thing" ladder conflicts with a required
  component: **keep the component**, keep the implementation minimal, and record
  the tension in `docs/decisions/`.
- Any deferred shortcut gets a `ponytail:` comment naming the upgrade path.

Commands: `/ponytail [lite|full|ultra|off]`, `/ponytail-review`,
`/ponytail-audit`, `/ponytail-debt`.

## 🕸️ graphify usage

Query the graph before grepping, once the repo is large enough for it to help.
For `apps/web` while it is small, plain grep is fine.

```
graphify query "how does the chat tool loop work?"
graphify path "search_portfolio" "send_message"
graphify explain "IngestionService"
graphify update .    # re-run after structural changes (code only, no LLM)
```

graphify is a **workflow experiment, not a necessity**. Say so honestly in
`docs/AI_USAGE.md`.

## 🗣️ Output style (caveman)

If caveman is enabled, it applies to chat replies only. Code, comments,
commit messages, ADRs, and everything in `docs/` are written in normal,
complete prose.

## 🛠️ Standards

**General**
- Never commit secrets. `.env` is git-ignored; ship `.env.example`.
- Free tiers only. Add `/health` that does **not** touch the DB (Neon must be
  able to scale to zero).
- Remove unused imports, variables, and `console.log` before committing.
- **Do not guess.** Batch questions to the user; do not ask one at a time.
- Verify third-party facts (free-tier limits, package names, CLI flags) against
  official docs or `--help` before relying on them.

**TypeScript / frontend**
- Functional components with typed props. Tailwind utility classes only (no
  inline styles, no CSS modules).
- No file over ~150 lines; split components before that.
- Colors, spacing, and type come from theme tokens, never hardcoded hex or
  pixel values.
- `components/ui` stays dumb (props in, JSX out). Data fetching and state live
  in feature hooks or `lib/api`.
- Prefer shadcn primitives over hand-built ones.
- Every data-driven component handles loading, empty, and error states.

**Python**
- Type hints on every function, small single-purpose modules, no duplicated
  logic, tests for every tool.