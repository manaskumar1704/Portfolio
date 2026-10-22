# Session retro — October 2026

Mined from the OpenCode session database, sessions Oct 8–22, 2026. Everything
below traces to a session prompt or closing summary; nothing is reconstructed
from memory. Written by the `/retro` workflow after the production deploy.

## Method

- **Source:** `%USERPROFILE%\.local\share\opencode\opencode.db` (SQLite), tables
  `session_v2` and `session_message`. Timestamps are Unix milliseconds; parent
  sessions carry their own prompts, child sessions are subagent work.
- **Tool:** `scripts/retro/retro_digest.py`, driven by the `/retro` command. It
  writes one digest file per parent session: every user prompt, the message-type
  census, and the last two assistant messages.
- **Corpus mined:** six parent sessions (26, 1, 1, 6, 6, 32 user prompts). No
  sessions for this project exist in the database before Oct 8.

## Timeline

| Session | Span (UTC) | Prompts | What happened |
|---|---|---|---|
| `tidy-harbor` | Oct 8 09:57 → Oct 11 19:52 | 26 | The backend plan session. Stack lock, the disciplines that became ADRs 0001–0011, corpus rules, email security, the acceptance-harness idea. Plan only — no code written here. |
| `crisp-squid` | Oct 19 16:28 → 16:38 | 1 | First `/graphify` run hits plugin error `err_b657c4fe` (default export). Four child extraction chunks, two retries. |
| `glowing-sailor` | Oct 19 16:45 → 16:53 | 1 | Graphify retry, same wall; the command file's heredoc ban comes from this pair. |
| `curious-circuit` | Oct 19 22:37 → Oct 21 09:25 | 6 | Features implementation plan: slash commands, contact drafts with caps, connector seams, tracing. 859 assistant messages, ten compactions. |
| `glowing-river` | Oct 21 11:02 → 16:14 | 6 | Fork of `curious-circuit` carrying the same plan; the feature build finished across the two. |
| `stellar-wolf` | Oct 21 16:46 → Oct 22 14:39 | 32 | Production readiness audit → deploy: `docs/DEPLOY.md` steps 1–18, live incident fixes, the eight-item smoke test, and the retro that became this document. |

## Decisions

| When | Decision | Where it lives now |
|---|---|---|
| Oct 8–11 | Stack lock: FastAPI + uv + Docker + Render free; Next.js + bun + shadcn/ui + Vercel; Neon Postgres + pgvector; no LangChain | `AGENTS.md` |
| Oct 8–11 | LLM providers behind an `LLMClient` interface; Gemini primary, Groq fallback; the tool-loop shape | ADR 0001, 0003 |
| Oct 8–11 | Postgres access shape; pooled vs direct URL split; additive migrations only | ADR 0002 |
| Oct 8–11 | Local ONNX-only embeddings to fit the 512 MB tier; hybrid retrieval; corpus heading levels are chunk boundaries and citation labels | ADR 0004, ingest |
| Oct 8–11 | GitHub tool allowlisted by exact `owner/repo` to `GITHUB_OWNER`; 404 and not-allowed indistinguishable; README excerpts treated as capped untrusted data | ADR 0005 |
| Oct 8–11 | Email is never a tool: model drafts only, approval token stored as SHA-256, bound to originating IP and expiry | ADR 0005, 0006 |
| Oct 8–11 | Markdown rendered inert (no raw HTML, scheme allowlist) | ADR 0007 |
| Oct 19 | Graphify determinism: only `scripts/graphify/pipeline.py`, the upstream skill's heredocs are banned | `AGENTS.md`, `.opencode/commands/graphify.md` |
| Oct 19–21 | Two external services (ThirdBrain, JobFinder) get typed seams now, implementations later; verified badge ships dark; tracing dark by default; per-IP daily send cap | ADR 0008–0011 |
| Oct 21 | Proxy trust is observed, not guessed: temporary header probe route → fill `TRUSTED_PROXY_CIDRS` → delete route | `.env.example`, `docs/DEPLOY.md` step 12 |
| Oct 22 | `/health` and `/ready` declare `methods=["GET","HEAD"]` explicitly; chat confirms a sent message; a repo without a README still lists | commits `d380a8c`, `dcd1c76`, `afe8728` |

## Stuck loops

| Loop | Repeats | Root cause | Fix | Where it lives now |
|---|---|---|---|---|
| PowerShell syntax inside the harness shell (`& $x`, multiline blocks, `ConvertFrom-Json`) | ~8 failure modes | the harness runs Git Bash; call operators and multi-line blocks crash or work only once it re-resolves its shell | one-line `;` chains, temp script files instead of inline quoting, no `& `$ | `.agents/skills/windows-shell-discipline/` |
| Git Bash `usr/bin` dropping off `PATH` mid-session; leading-slash arguments path-mangled; case-insensitive matching false-positives (`"Not found."` vs `"Not Found"`) | several per session | Git Bash environment and path-translation rules | PATH repair line at call start, exact string compares, raw output before filtered output | same skill |
| Alembic receiving `&& uvicorn ...` as its own arguments (deploy boots crash, exit 2) | 1 outage | free tier has no `preDeployCommand`; Docker `CMD` has no shell | `sh -c "alembic upgrade head && exec uvicorn"` | `.agents/skills/free-tier-deploy/` |
| Green checks, production unchanged | 1 long afternoon | a failed boot keeps the previous image serving | consult the deploy log and deployed behaviour, not the check runs | same skill |
| `/health` returning 405 on HEAD | 2 live hits | FastAPI 0.143 + Starlette 1.7 no longer derive HEAD from GET | explicit `methods=["GET","HEAD"]`, pinned by `test_health_answers_head`, reproduced locally with TestClient first | commit `d380a8c` |
| `/32` trusted-proxy CIDR rejected | 1 | Render rotates its internal proxy peer on every deploy | `10.0.0.0/8` plus Cloudflare's published ranges; observe via probe route then delete it | `.env.example`, skill |
| Neon password reset, wrong scope | 1 outage | resets are branch-scoped, not global | reset the production branch's `neondb_owner` in the console, re-point pooled and direct URLs | skill, `docs/DEPLOY.md` |
| Graphify plugin default-export error | 2 sessions, 12 child retries | upstream skill's bash heredocs never survive the harness | `pipeline.py` per stage; `/graphify` forbids heredocs | `AGENTS.md` |
| CI test fails on the machine's own `.env` | 1 | same-named environment variables leak into imported config | clearing ambient env in the test fixture | api tests |
| Overbroad ignore glob deleting intended files (`.vscode/extensions.json`, untracked `.agents` skills) | 2 | glob too wide | explicit re-includes, review the diff before committing | commits `1b7f287`, `b4ddc40` |
| Free model drift mid-session (e.g. `fledge-alpha-free` vs `mimo-v2.6-flash-free`) | 5–6 switches | harness model routing re-resolves; skills' model claims age | verify the model id against the provider's own list endpoint before relying on it | `AGENTS.md` Gemini rules |

## Learnings → artifacts

| Learning | First paid for by | Artifact |
|---|---|---|
| Shell discipline rules for the harness | `tidy-harbor` → `stellar-wolf`, recurring | **Done:** `windows-shell-discipline` skill |
| Free-tier deploy mechanics: CMD-wrapped migrations, failed boot keeps old image, `checksPass` cadence, monitors default to HEAD, cron throttling, proxy rotation, branch-scoped Neon resets, pooled vs direct | `stellar-wolf` | **Done:** `free-tier-deploy` skill |
| Retros mined from the session database, not memory | this retro | **Done:** `scripts/retro/retro_digest.py` + `/retro` command |
| A digested document must exist before a skill that cites it | Oct 22 (skill referenced the not-yet-written retro) | **Done:** this file |
| Verify third-party facts (model ids, tier limits, CLI flags) against official sources | `crisp-squid` Neon doc fetch; audit week | **Done:** standing rule in `AGENTS.md` since the plan session |
| Reproduce locally with a throwaway script before touching production | `stellar-wolf` (TestClient HEAD repro, header probe) | reflected in the skill's verification order |
| Acceptance harness for agent work: frozen versions, blind grading, pre-registered criteria | `tidy-harbor` Oct 11 | `skills-lock.json` pins vendored skill sources reused here |

## Honest limits

- Assistant messages were sampled (last two per session); tool-call streams
  were not replayed. Loops are therefore visible through prompts, closers, and
  child-session titles, not through every intermediate step.
- Early prompts in compacted sessions are summaries, not verbatim text.
- Nothing before Oct 8 exists for this project in this database; the Oct 5–7
  thinking lives in the repo's `docs/decisions/` records only.
- The digest files live in the temp directory and are regenerable with the
  `/retro` command at any time.
