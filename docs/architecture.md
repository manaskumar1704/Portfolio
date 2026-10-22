# Architecture

The system as it currently runs, with the live processes and every action the
agent can take. One line per box: what it is, what it does, why it exists. The
quick request-flow narrative lives in the README; this page is the map.

```mermaid
flowchart TB
  %% ── Live on the dev machine right now ──
  BR["1 · Browser (Chrome / Playwright)<br>what: the visitor's console<br>does: renders the site, opens the SSE stream<br>why: the product surface"]:::live
  ND["2 · next dev — :3000<br>what: Next.js 16 + Turbopack (App Router)<br>does: pages, slash-command palette, streamed chat log<br>why: dev iteration + SSR shell"]:::live
  UV["3 · uvicorn --reload — :8000<br>what: FastAPI app (apps/api)<br>does: /chat SSE, /health, send route, rate limit, CORS allowlist<br>why: the whole backend brain"]:::live
  OS["4 · opencode serve --service (PID ~36712)<br>what: this agent's background helper<br>does: polls local /health + /v1/models every 30 s<br>why: self-check; the /v1 404s it logs are harmless"]:::live

  %% ── In-process layers of the API ──
  FO["5 · FailoverClient (in-process)<br>what: retry + provider-swap wrapper<br>does: retries the provider per attempt, finishes on Groq after the budget<br>why: a 429 must not kill a visitor's answer"]:::layer
  TL["6 · Tool loop (in-process)<br>what: run_chat_turn() — one function, an async generator<br>does: model → tool calls → registry → results back to the same interaction<br>why: the loop is the spine; state is local, so evals call it directly"]:::layer
  RG["7 · Tool registry (in-process)<br>what: the security boundary<br>does: search_portfolio · get_github_repo · draft_message; errors as data<br>why: the model can only do what the registry exposes"]:::layer
  RR["8 · Hybrid retrieval (in-process)<br>what: one SQL statement, one round trip<br>does: vector RANK + websearch ts_rank_cd + RRF fusion, gate MIN_RRF_SCORE=0.02<br>why: dense-only lied — off-topic ranked closer than on-topic"]:::layer

  %% ── Remote ──
  NE["9 · Neon Lakebase Postgres<br>what: pooled + direct endpoints, pgvector(384)<br>does: chunks (23 from 6 corpus files — the current slate), drafts, tokens, send caps<br>why: storage that scales to zero on the free tier"]:::remote
  GM["10 · Gemini API<br>what: gemini-3.5-flash-lite via google-genai ≥ 2.25 interactions API<br>does: provider-side tool calling on a conversation the API remembers<br>why: primary — cheapest tier that does grounding properly"]:::remote
  GQ["11 · Groq API<br>what: openai/gpt-oss-120b, OpenAI-compatible shapes<br>does: fallback legs on switch<br>why: survives Gemini 429s (local key currently dead — Render's works)"]:::remote
  RE["12 · Render free API — portfolio-api-59on.onrender.com<br>what: the deployed prod image of this same API<br>does: prod traffic; sleeps after 15 min → the waking cycle<br>why: free hosting; CORS still lacks localhost:3000 (dashboard fix pending)"]:::remote
  VE["13 · Vercel — manas-dev.vercel.app<br>what: deployed Next.js build<br>does: prod frontend, browser → Render direct fetch<br>why: prod home of the portfolio"]:::remote
  RS["14 · Resend<br>what: email provider<br>does: sends ONLY on the approved send-route call<br>why: email is never a tool — approval-gated by design"]:::remote
  LF["15 · Langfuse<br>what: trace sink, optional via env<br>does: spans per leg/tool/turn<br>why: answer observability; silent 401s when unset — noise only"]:::remote
  GH["16 · GitHub API<br>what: public repo fetch<br>does: get_github_repo, allowlisted to GITHUB_OWNER<br>why: cited repo data without trusting the model"]:::remote

  %% ── Batch-time, not serving ──
  IN["17 · ingest/run.py<br>what: corpus → chunk → embed → upsert batch job<br>does: mirrors a corpus dir into Neon chunks<br>why: the agent's knowledge has no other source"]:::batch
  EV["18 · evals/ (pytest)<br>what: golden sets — retrieval, answers, groundedness NLI<br>does: graded behaviours incl. the off-topic redirect cases<br>why: regressions must fail loudly, not silently"]:::batch
  MC["19 · mcp/ overlay (idle)<br>what: MCP server importing app tools<br>does: exposes the same registry to any MCP client<br>why: showcase layer; imports, never copies"]:::batch
  GR["20 · graphify pipeline (idle)<br>what: code knowledge-graph builder<br>does: 2513 nodes / 4804 edges over this repo<br>why: architecture queries like this document's basis"]:::batch

  %% ── Edges ──
  BR -->|"opens, dismisses landing"| ND
  ND -.->|"streamed HTML + client JS"| BR
  ND -->|"POST /chat (SSE), /health ping, status line in the log"| UV
  OS -.->|"/health 200 · /v1/models 404, every 30 s"| UV
  UV --> TL
  TL --> FO
  FO -->|"interactions.create + retries"| GM
  FO -->|"after LLM_MAX_ATTEMPTS"| GQ
  TL -->|"validated args + registered handlers only"| RG
  RG -->|"embeds query, gates, dedupes citations"| RR
  RR -->|"SELECT over chunks"| NE
  RG -->|"draft_message → pending row, no token to the model"| NE
  RG -->|"get_github_repo"| GH
  NE -->|"pending row + approval_token + IP match"| RS
  BR -.->|"stopped copy runs on prod via env"| VE
  VE -->|"NEXT_PUBLIC_API_URL"| RE
  RE -->|"prod DB + prod keys"| NE
  RE -->|"send route"| RS
  LF <-.->|"OTLP spans (401s until keys exist)"| UV
  IN -->|"batch upserts"| NE
  EV -->|"measures TL + RR directly (no HTTP)"| TL
  MC -.->|"python imports"| RG
  GR -.->|"reads the repo"| ND

  classDef live fill:#1d2a35,stroke:#3aa8c1,color:#e8eef2;
  classDef layer fill:#223024,stroke:#5aa87a,color:#e8eef2;
  classDef remote fill:#251f2e,stroke:#9a7ad4,color:#e8eef2;
  classDef batch fill:#2b2620,stroke:#c1903a,color:#e8eef2;
```

## Known gaps (as of 2026-10-23)

- **Corpus slate**: the ingested corpus is `corpus/local/` = 6 documents / 23
  chunks. Missing standalone `skills.md`, `resume.md`, and `contact.md` means
  `/skills`-shaped prompts depend entirely on the profile doc's overlap and
  can honestly miss — the `/skills` diagnosis (2026-10-22) ended there, not in
  a bug. Real documents come from the owner; `_test/` fixtures are never
  ingested.
- **Recall ceiling**: `MIN_RRF_SCORE = 0.02` requires both retrievers to
  agree (decision 0004). Compound queries whose words the corpus does not
  carry starve the lexical leg and score at most 0.0164 before the gate —
  the agent's tool description now nudges it to retry shorter instead of
  widening the gate; recalibration lives in `evals/` on the real corpus.
- **Render CORS**: the production instance still lacks
  `http://localhost:3000` in `CORS_ORIGINS`, so the local browser against the
  live API is a Vercel-only story until the dashboard value is updated.
- **Langfuse**: unset locally, so the OTLP exporter retries and logs 401s —
  noise, no functional impact.
