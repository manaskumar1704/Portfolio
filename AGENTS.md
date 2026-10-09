# Agents & Tech Stack Lock

Project: chat-first AI portfolio. Spec: this file, plus the phase plan the
user approved in session. Backend builds in slices, one phase per prompt.

## 🔒 Locked Tech Stack

**Do NOT introduce new libraries without explicit user approval.** Add it to
`docs/decisions/` first with a one-paragraph justification.

| Layer | Choice |
|---|---|
| Frontend | Next.js (App Router), shadcn/ui, Tailwind, Bun, Vercel |
| UI vibe | Terminal / Claude Code-like, monospace-forward |
| API | FastAPI, managed with uv, Docker, **Render free web service** |
| Database | **Neon** Postgres + pgvector. **Not** Render Postgres (expires in 30 days) |
| LLM (app runtime) | **Gemini `gemini-3.5-flash-lite`** primary, Groq (`openai/gpt-oss-120b`) fallback. Behind an `LLMClient` interface |
| Gemini SDK | `google-genai` >= 2.25. Never the deprecated `google-generativeai` |
| Embeddings | Small local model (fastembed), must fit 512 MB RAM |
| Evals | pytest runner in `evals/` |
| Tracing | Langfuse |
| Email | Resend |
| MCP | Official Python MCP SDK |
| CI | GitHub Actions |

No LangChain. Native provider tool-calling, behind `LLMClient`. Tool-calling is
the spine; RAG is one tool; MCP is a separate showcase layer that **imports**
from `apps/api`, never copies.

## 🤖 Gemini skills — load when working on `app/services/llm.py`

`.agents/skills/` holds Gemini skills. **Load `gemini-api-dev` before writing or
changing any Gemini code.** They override training data: model names, SDK
surface, and event shapes in this area change faster than anything else here.

- `gemini-api-dev` — text, streaming, **function calling**, structured output.
  Required for the chat endpoint and any change to `GeminiClient`.
- `gemini-live-api-dev` — bidirectional audio/video streaming. **Not used by
  this project.** Do not add a Live dependency for a text chat.
- `gemini-omni-flash-api` — video generation. **Not used by this project.**

Model rules from those skills that bind this repo:

- **Never `gemini-2.5-*`, `gemini-2.0-*`, `gemini-1.5-*`.** Legacy and
  deprecated.
- Use `google-genai` >= 2.25. Never `google-generativeai`.
- SDK >= 2.0 uses the Interactions schema. The `interactions` surface is what
  `GeminiClient` calls; keep it that way rather than reaching for
  `generateContent` directly.
- Verify a model id exists before relying on it:
  `curl "https://generativelanguage.googleapis.com/v1beta/models?key=$GEMINI_API_KEY"`
  Models listed in a skill are not a guarantee.

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
apps/api     FastAPI backend
  app/core       config, logging, tracing, ratelimit, guardrails
  app/api        routers only; no business logic
  app/services   capabilities as plain functions (rag, github, contact, llm)
  app/tools      thin wrappers exposing services to the model + MCP
  app/db         pool, session, models, queries
  app/schemas    Pydantic request/response models
  ingest/        corpus -> chunk -> embed -> upsert (batch, not served)
design/      Open Design export, reference only
corpus/      Markdown source of truth for RAG
  _test/     FICTIONAL fixture corpus, never ingested into the real one
  _source/   PDFs, git-ignored. Convert with ingest/from_pdf.py
evals/       Golden set + runner
mcp/         MCP server (imports from apps/api tools)
docs/        AI_USAGE.md, decisions/ ADRs, frontend-plan.md
scripts/     Dev tooling, not shipped
  graphify/  pipeline.py, the stages behind /graphify
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
graphify path "search_portfolio" "draft_message"
graphify explain "IngestionService"
graphify update .    # re-run after structural changes (code only, no LLM)
```

Building the graph is `/graphify .`. That custom command (`.opencode/commands/
graphify.md`) drives `scripts/graphify/pipeline.py`, one stage per subcommand:
`detect ast cache merge build health labels html finalize clean`. The upstream
skill's bash heredocs do not survive PowerShell quoting, so use the script, not
the skill's inline code.

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
- **Email is never a tool.** The model may call `draft_message` to write a
  `pending` row. Sending is a plain HTTP route requiring an unguessable
  `approval_token` plus a matching originating IP. The model has no send tool
  and no way to read the token.
- Remove unused imports, variables, and `console.log` before committing.
- **Do not guess.** Batch questions to the user; do not ask one at a time.
- Verify third-party facts (free-tier limits, package names, CLI flags) against
  official docs or `--help` before relying on them.

**TypeScript / frontend**
- **React work:** load the `vercel-react-best-practices` skill before writing,
  reviewing, or refactoring any React or Next.js code (components, hooks,
  data fetching, rendering, bundle size, performance).
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

**Corpus (never invent facts)**
- The real corpus is the user's, in a separate repository, pointed at by
  `CORPUS_DIR`. Do not write résumé content, employers, dates, metrics, or
  contact details. If a fact is missing, say so.
- `corpus/_test/` is fictional and labelled as such on every file. It exists only
  so retrieval tests have concrete assertions. Never point the real ingest at it.
- `corpus/_source/` holds PDFs and is git-ignored. Convert with
  `ingest/from_pdf.py`; commit the Markdown, never the PDF.
- Heading levels are load-bearing. The chunker uses `#`/`##` as chunk boundaries
  and carries them through as citation labels.
- PDFs lose two things silently: heading structure and word integrity. Both are
  checked by `ingest/from_pdf.py`, which exits non-zero rather than writing a
  file that retrieves badly.

**Retrieval**
- Retrieval is hybrid (lexical + dense, RRF-fused), not dense-only. Measured:
  dense-only ranked off-topic questions *closer* than on-topic ones, so the tool
  could not honestly report "nothing matched".
- `ONNX` embeddings only. No sentence-transformers, no PyTorch — Render free is
  512 MB. The measured container peak is 267 MB with the model loaded.
- The BGE query instruction goes on queries, never on documents, and is applied
  by hand: `fastembed`'s `query_embed` does not add it. There is a test pinning
  that behaviour, so do not "simplify" it away.
- The embedding model is baked into the Docker image at build time. A cold start
  must never wait on a download.