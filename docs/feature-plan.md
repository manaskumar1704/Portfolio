# Feature plan — checkpoints 0–5 (approved 2026-10-20)

Extends the shipped portfolio app with the features proposed in session. This
file records the plan the user approved, the measured facts it rests on, and the
skills to load per checkpoint. `docs/frontend-plan.md` still governs the
frontend design system; `docs/DEPLOY.md` governs deployment; nothing here
overrides those, and where a checkpoint touches them the change is listed.

## Decisions taken in session (binding)

1. **Connectors are idle, not live.** ThirdBrain and Job Finder arrive as typed
   seams with mocked implementations. No endpoint, no auth, no live HTTP until
   the user supplies each contract. The tension with the ponytail ladder (an
   interface with one implementation and no callers) is deliberate: the user
   asked for "idle connectors to add that future part". Recorded in ADR 0008.
2. **The NLI check lives in the Job Finder API later.** It is not computed in
   this repo's request path. Measured why: int8 NLI is 79 MB, 5 pairs = 1.41 s
   here ≈ 14–28 s on Render free 0.1 CPU, and against chunk-sized premises it
   answers *neutral* even for supported claims. NLI runs offline in the eval
   harness, where CPU and RAM are free.
3. **The live badge is dark this release.** No cheap local check discriminates:
   cosine of supported claims 0.67–0.81 vs fabricated 0.42–0.71; lexical
   coverage of true claims 0.64–1.00 vs fabricated 0.42–0.71 — both overlap.
   The model emits no paths or `[n]` markers in prose (measured on 5 live
   answers), so there is nothing to match on. `sources_verified` exists in the
   contract and stays `false` until a real verifier is wired; the badge renders
   only when it is true.
4. **Slash commands prompt the LLM.** `/skills`, `/projects`, `/resume` expand
   to their natural-language question and go down the normal streaming path —
   same citations, same quality. `/contact` opens the local form. `/help`,
   `/clear` and unknown commands stay local. `/compare-jd` is a placeholder
   reply with no LLM call until Job Finder is wired.
5. **Per-IP daily send cap:** a separate `ip_send_counters(day, ip_hash, count)`
   table, same `ON CONFLICT` shape as `send_counters`. It retains a salted IP
   digest for one day — tradeoff recorded in ADR 0011.
6. **Draft APIs name the visitor address `sender_email`.** The `Message` row,
   the `draft` SSE event, the draft tool argument and `DraftSummary` all use
   one vocabulary. The model-facing tool argument stays `email` — renaming tool
   args changes the schema sent to the provider for no visitor-visible gain.
7. **`/compare-jd` dead end is acknowledged in the landing copy:** a line
   pointing at `/help` so the placeholder never looks broken to a visitor.

## Skills to load per checkpoint

From `.agents/skills/`, per AGENTS.md ("load before writing in that area"):

| Checkpoint | Skills | Why |
|---|---|---|
| 0 | `gemini-api-dev`; `vercel-react-best-practices`; `playwright-cli` | chat route + event plumbing; the two missing `lib/api` modules; screenshot the repaired approve flow |
| 1 | — | pure backend seams, no Gemini code, no UI |
| 2 | `vercel-react-best-practices`; `playwright-cli` | `use-agent.ts` composer intercept; verify type-in behaviour |
| 3 | `gemini-api-dev`; `vercel-react-best-practices`; `playwright-cli`; `neon-postgres` | `done` event emitters, badge UI state, fixture-corpus DB work |
| 4 | `neon-postgres`; `playwright-cli` | migrations (enum value, new columns), then exercise the lifecycle |
| 5 | `neon-postgres` | `ip_send_counters` table, retention sweep |
| never | `gemini-live-api-dev`, `gemini-omni-flash-api` | AGENTS.md: not used by this project |

Not assigned: `design-taste-frontend`, `high-end-visual-design`, `imagegen-*` —
the badge is dark this release and no new screens are designed. If a real badge
ships later, load them then.

## Checkpoint 0 — repair the base

Everything else assumes this. Four defects, all measured end-to-end:

### 0.1 the approve path is broken in production

`contact.create_draft` writes plaintext `origin_ip` and never `ip_hash`; the
registry calls handlers with model args only, so the IP never reaches the
service; `messages._ip_matches()` compares `ip_hash … = ip_hash`, and Postgres
NULL != NULL, so every approval 403s ("approval refused: different network").
The suite passes only because `tests/helpers.make_pending_draft` writes
`ip_hash` directly.

Fix at the root, one place, no tool-arg IP:

- `create_draft` writes `ip_hash = hash_client_ip(origin_ip, settings)` and
  stops writing plaintext `origin_ip` (column stays, nullable, per ADR 0006).
- The chat route passes the resolved `client_ip` into the tool loop **outside
  the model's view**: a `ContextVar` (mirrors the existing `request_id` one),
  not a tool argument the model could forge.
- A migration records the relaxation; existing NULL-bound drafts keep failing
  closed, which is correct.
- Every approval now genuinely requires: unguessable token, matching salted
  IP hash, unexpired row, `pending` status.

### 0.2 eight integration failures

`uv run pytest -q -m integration` → 8 failed / 41 passed. Seven are
`test_contact_db.py` calling the deleted `get_draft_for_approval`; one is
`test_schema.py` asserting `origin_ip` was NOT NULL, relaxed by
`c3d4e5f6a7b8`. Replace the seven with tests that drive the live path:
create → send with same IP refuses nothing, different IP refuses, expired
refuses, already-sent refuses single-use. Keep the all-arg-object style, one
fact per test.

### 0.3 the frontend does not build

Commit `4e5b529` shipped red tests as specification: `parse-sse.ts` and
`draft-approve.ts` are deliberately missing. `next build` fails on module
resolution, `tsc --noEmit` has 4 errors, `bun test` is 6 pass / 2 fail.

Implement both modules to their test specs, no more:
- `parse-sse.ts` — incrementally parse `text/event-stream` frames into typed
  `ChatEvent`s, tolerating partial frames across chunk boundaries.
- `draft-approve.ts` — POST the approval token to `/messages/{id}/send`.

Then: `bun run typecheck`, `bun test`, `bun run build` all green. Screenshot
the chat and approve flow against `design/` with playwright-cli.

### 0.4 no supported way to load the fixture corpus

`corpus/_test/README.md` documents `uv run python -m ingest.run --dir
../../corpus/_test`, which the guard in `discover()` now refuses. The 20
fixture chunks in the dev DB predate the guard. Evals (CP3) need fixtures.

Fix: a dedicated `ingest/fixtures.py` that hardcodes the corpus/_test file
list and calls `run_ingest(directory, files=…)` — the existing explicit-list
door — so `discover()` and its guard stay untouched, and the old hole (loading
fiction into a real corpus) stays closed. Update the fixture README to point
at it. Dev DB holds only fixtures, production holds only the real corpus;
separation stays by database.

**Acceptance:** `pytest -q -m integration` green; `bun test` + `typecheck` +
`build` green; a real draft can be approved end-to-end against the dev DB.

## Checkpoint 1 — idle connectors

`app/services/connectors.py`, the future plug-in points (ADR 0008):

- `JobFinderConnector` — `verify_grounding(answer, snippets) -> Verdict`; the
  NLI check arrives as this one method when the contract exists. Job lookups
  are added later too.
- `ThirdBrainConnector` — corpus search, once the corpus moves out of the repo.

Both: typed Protocol, a mock implementation returning fixture data, tests
proving safe error results on timeout/non-200/malformed JSON, and capped,
labelled responses (same "untrusted data" rule as `github.py`'s README). No
live HTTP, no credentials, no config keys.

## Checkpoint 2 — slash commands

- Update `docs/frontend-plan.md` §3 first: these are *prompt aliases*, not the
  `ls`/`cd`/`cat` navigation registry that was removed; the link-navigation
  stance stands.
- `app/services/prompts.py` (backend) holds the expansion table;
  `lib/api/commands.ts` mirrors it for local commands. Expansion is a pure
  Bun-testable table: `command → { kind: "prompt" | "local" | "clear" }` — the
  project has no DOM test environment (adding one needs an ADR).
- `/skills` `/projects` `/resume` → expanded prompt → normal streaming path
  (citations included). `/contact` → open the local form (CP4). `/help` /
  unknown → local help, no LLM call. `/clear` → clears the transcript locally.
  `/compare-jd` → local placeholder answer, honest, no LLM call.
- Landing copy gains the point-at-`/help` line so `/compare-jd` doesn't read as
  broken.

## Checkpoint 3 — verification + evals

- `SourceVerifier` Protocol; `CorpusPathVerifier` ships (cited paths must
  resolve); `JobFinderNliVerifier` is the future drop-in behind the same
  interface. **No verifier is wired in production this release** — the badge
  stays dark (decision 3).
- `done` event gains `sources_verified: bool` in **both** emitters —
  `services/chat.py` and the error-path fallback in `api/chat.py:143`, which
  today also omits `text_length` against a `types.ts` type that requires it.
  Contract test extends from event names to field names on `done` (and on the
  draft event, which already pins `approval_token`).
- `evals/` at repo root (AGENTS.md layout; `render.yaml` already ignores
  `evals/**`). Runner: `uv run --project apps/api pytest evals`, `apps/api` on
  `pythonpath`. Golden set over the fixture corpus: supported questions,
  off-topic abstention, source matching, untrusted-input handling, and NLI
  groundedness scored **offline** with the int8 model (`slow` marker;
  downloaded in CI only; never in the API image).
- New labelled fixture `corpus/_test/injection.md` — the corpus has no
  instruction-shaped text today, so the untrusted-input eval has nothing to
  assert against. Loaded only via `ingest/fixtures.py`.

## Checkpoint 4 — the contact draft lifecycle

- One draft service, two issuers: the `draft_message` tool and a new
  `POST /messages/drafts`. Both bind `ip_hash` at create time; the plaintext
  token goes to the browser only, its SHA-256 stored server-side.
- **Create issues the token, it doesn't require one** — protected by the
  existing per-IP limiter + IP binding. Edit (`PATCH /messages/{id}`), cancel
  (`POST /messages/{id}/cancel`) and send require: token (constant-time
  compare), matching IP, unexpired, `pending`. One token per draft, not
  rotated on edit.
- `cancelled` becomes a real status: enum migration (recreate-the-type pattern
  from `c3d4e5f6a7b8`), `MESSAGE_STATUSES` updated,
  `test_no_send_in_p6.py`'s exact-set assertion updated, and **retention taught
  the new status** — today it sweeps `('pending','sending')`, `'pending'` and
  `('sent','failed')`, so cancelled rows would never delete.
- Migration adds `company`, `role`, `subject`.
- CORS gets `PATCH` (`allow_methods=["GET","POST"]` would block the browser).
- `sender_email` vocabulary everywhere visitor-facing (decision 6); the
  model-facing tool argument stays `email`.
- Offline-capable pieces get their fixture jury test; lifecycle exercised with
  playwright-cli against the dev DB.

## Checkpoint 5 — limits, observability, deployment

- Chat limit 10 → 15/min per IP. Three places: `config.py` default,
  `.env.example`, and `render.yaml` — the last pins `RATE_LIMIT_PER_MINUTE:
  "10"` explicitly, so the default change alone would never reach production.
  Burst to 15 to match.
- `ip_send_counters(day, ip_hash, count)` for two per-IP sends per UTC day
  (decision 5). Reserve before send, release on failure, atomic
  `INSERT … ON CONFLICT … DO UPDATE … WHERE count < cap`, swept by retention.
- Langfuse (`langfuse==5.0.3`, OpenTelemetry-based) behind the settings that
  already exist; no-op when keys are absent. Traces: timing, token usage, tool
  outcomes, source presence — never message text, approval tokens or
  credentials. **ADR 0010 before the dependency lands**, per AGENTS.md.
- CI gains the frontend job (`bun test`, typecheck, build) and an evals job;
  neither exists today.
- `preflight.sh` gains a contact-lifecycle smoke (create → edit → cancel; no
  mail sent).

## Ponytail process (per AGENTS.md scope rule)

- Every checkpoint ends with `/ponytail-review`; findings are implemented in
  the same checkpoint; the checkpoint's tests re-run green after.
- Checkpoint 4 additionally ends with `/ponytail-audit` (whole-repo
  over-engineering scan); findings triaged then recorded, not silently dropped.
- Required components (RAG, tool-calling, MCP server, evals, tracing, CI) are
  never "simplified away"; where the ladder pushes against one, keep it minimal
  and record the tension in `docs/decisions/`.

## Not in this plan (still owed)

- The MCP server (`mcp/` importing from `apps/api` tools) — AGENTS.md lists it
  as a required showcase deliverable; it stays owed until a checkpoint covers
  it.
- `docs/AI_USAGE.md` — owed by AGENTS.md (graphify is a workflow experiment,
  say so honestly there).
- Live connector wiring — the moment real endpoints/auth arrive, CP1's mocks
  are replaced by HTTP implementations behind the same Protocols.
- Lighting the badge — when Job Finder's NLI endpoint is callable, set the
  verifier, load `gemini-api-dev` + `neon-postgres`, and remove the dark-badge
  ADR line.
