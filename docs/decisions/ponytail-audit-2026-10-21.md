# Ponytail audit — checkpoint 4 (2026-10-21)

One-shot whole-repo scan at the end of checkpoint 4, per the plan's process
section. The audit listed 26 findings (`net: -335 lines, -2 deps` before
triage). This file is the triage: what was applied in the same checkpoint and
what was deliberately kept, with the reason. Nothing silently dropped.

## Applied

| Finding | Where | Note |
|---|---|---|
| Unused `ip_hash` in `claim_pending`'s RETURNING | `apps/api/app/db/queries/messages.py` | send reads six keys, never this one; `mark_sent` nulls it in SQL. |
| `_utcnow()` one-caller wrapper | `apps/api/app/api/messages.py` | inlined as `datetime.now(UTC)`; codebase style everywhere else. |
| `DraftSummary` built twice | `apps/api/app/api/messages.py` | shared `_summary(row)` helper for GET and PATCH. |
| 429 block copy-pasted ×4 | `apps/api/app/api/messages.py` | `_too_many()` helper; no pin on the wording existed. |
| `createDraft` unused `signal?` param | `apps/web/src/lib/api/drafts.ts` | zero callers pass it. |
| `CancelDraftResponse.reason` never set | `apps/api/app/schemas/message.py` | refusals raise instead of filling a reason. |
| DraftApproval terminal branches never paint | `apps/web/src/features/contact/draft-approval.tsx` | both parents unmount the card in the same commit as the callback; the component now settles to `null` and the parents own the words ("Sent — thank you." / card gone). `.draft-sent`/`.draft-withdrawn` CSS deleted; `.draft-tick` moved to the form's sent line. |
| `_too_many` + limiter wordings unified | `apps/api/app/api/messages.py` | see above; one wording on every route. |
| `chat.ts` re-export file, zero importers | `apps/web/src/lib/api/chat.ts` | deleted. |
| `cn` package, one call site | `apps/web/src/components/ui/reveal.tsx` | inlined template literal; dep removed. |
| `lucide-react`, one icon | `apps/web/src/components/ui/composer.tsx` | inline `<svg>` copied from its `ArrowUp`; dep removed. |

## Kept, with the reason

- **GET `/messages/{id}` + PATCH `/messages/{id}`** — the audit calls them
  browser-unreached. Kept: the plan's lifecycle checkpoint defines edit as a
  first-class capability exercised by tests; CP5's `preflight.sh` smoke drives
  create → edit → cancel through exactly these routes. Cutting them would
  delete the deliverable, not dead weight.
- **`echo` tool in the registry** — 15+ loop tests name it; replacing every
  fake with `search_portfolio` seams is its own slice, not an audit finding.
  Recorded for a cleanup checkpoint.
- **`_approvals.check` + `_too_many` fold into one `_gate()`** — kept unfolded
  deliberately: `test_rate_limiting_happens_before_the_token_check` asserts,
  structurally, that the limiter precedes the token check in each route's
  source. Folding hides the check inside a helper and the guard with it. The
  test is worth more than the lines.
- **retention `dry_run` predicate duplication (~20 SQL lines)** — `dry_run`
  and `sweep_once` intentionally never share a code path: the dry run must be
  provably read-only. A shared fragment would make that guarantee harder to
  see for 20 saved lines.
- **`ingest/fixtures.py` filter re-listing** — CP0's decision: fixtures use the
  explicit-list door so `discover()`'s guard stays out of them. Intentional.
- **`_token_lookup_sql()`** — kept as the function whose docstring explains why
  the hash-digest comparison is subtle; inlining buries it mid-`authorise`.
- **Dead settings/fields/functions** (`probe_enabled`, `mcp_auth_token`,
  `summarise_for_log`, `call_search_playlist`, `is_async_handler`,
  `ChatStreamError`, `embed_documents_async`, `reset_model`,
  `GroqClient.aclose`/`ENDPOINT`, token counts, `origin_client` param,
  `RetrievedChunk.distance`, `_discover_async`, Fs schemas) — all real, all
  from checkpoints 0–3, none blocking CP4. Cut in one dedicated cleanup slice
  rather than mid-checkpoint.
- **`chunks.token_count` and `origin_ip` columns** — dead since earlier
  relaxations. Next migration, deliberate data change with the enum/columns
  ones, not a code-only change.

## Graph-informed re-audit (2026-10-21, after checkpoint 5)

The knowledge graph (`scripts/graphify/pipeline.py`, full rebuild over the
CP4+CP5 state) was used as the scan's index rather than a fresh manual crawl.
Its structural signals: no import cycles; exactly one zero-inbound callable
(after triage a false positive — a test double's method, invisible to the AST
extractor); symbol duplication across files all attributable to convention
(alembic `upgrade`/`downgrade`, `main` entry points), deliberate TS↔Python
schema mirrors, or self-contained per-module test doubles.

One real finding was applied:

- **`ready_db` fixture, identical in five test files** — `test_pool`,
  `test_rag`, `test_schema`, `test_contact_db`, `test_verify` each carried a
  byte-identical `setup → yield pool → teardown` block. Now defined once in
  `tests/conftest.py`; the four files that used `pool` nowhere else also lost
  the import. Evals' two copies are kept: `evals/` is a separate root, and the
  live-answers version genuinely differs (it binds `current_client_ip` and
  wipes draft rows).

Checked and left alone: the three `make_settings` helpers share only a name —
email's mutates the settings singleton, client_ip's and github's construct
`Settings` with different required fields; they are three fixtures, not
copies. The CP0–3 dead-symbol list from the applied/kept table above (probe
route leftovers, `mcp_auth_token`, `RetrievedChunk.distance`, the `Fs*`
schemas, `chunks.token_count`, `origin_ip`, and the rest) remains owed to a
dedicated cleanup checkpoint; the re-audit adds nothing to it and removes
nothing from it.

Resulting counts: api 391 passed, web 54 passed, evals 19 passed (non-slow),
ruff clean.
