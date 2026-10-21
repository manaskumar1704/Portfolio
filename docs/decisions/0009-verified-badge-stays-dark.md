# 0009 — The verified badge ships dark: no verifier qualifies

Checkpoint 3, with the measurements from the phase-8 work that motivated it.

## The decision

`done.sources_verified` is in the wire contract from checkpoint 3 onward, in
both `done` emitters, and it is `false` until a verifier is wired. The
frontend badges it only when it is true. Nothing reports "verified" this
release, from anywhere, for any price. The interface
(`SourceVerifier` + `CorpusPathVerifier` in `app/services/verify.py`) is
completed and tested so the day a verifier qualifies, wiring is one assignment.

## What was measured, and why everything handy failed

An honest badge needs a check that separates answers actually grounded in
cited chunks from confident fabrications. Each candidate was measured on the
fixture corpus before this ADR:

- **Cosine** to the nearest chunk: supported claims scored 0.67–0.81,
  fabricated ones 0.42–0.71. **The ranges overlap.** No threshold separates
  them, so the check would randomly bless fabrications.
- **Lexical coverage**: true claims 0.64–1.00, fabricated 0.42–0.71 — again
  overlapping. Fusing both does not help; they correlate, and the fabricated
  band hides inside the supported one.
- **NLI (int8 cross-encoder, `cross-encoder/nli-distilroberta-base`)** on
  chunk-sized premises answered *neutral* for everything — supported claims
  included. The harness works (`evals/test_groundedness_nli.py`, ~170 ms per
  pair offline) and sentence-level premises classify cleanly; chunk-sized
  retrieval passages, which is what the loop would actually check, blur.
  79 MB model + 5 pairs ≈ 14–28 s on Render free 0.1 CPU ends any thought of
  running it per-answer in the request path.
- **Prose citations**: the model emits no `[n]` markers and no paths in
  answers (measured on 5 live answers), so there is nothing in the text to
  match `source_path` against.

Four independent candidates, four "cannot honestly fire" outcomes. The badge
is a claim of verified grounding; with no honest verifier, "verified" is
either a lie or a placeholder nobody can distinguish from a lie.

## What ships instead

- The field, the parser mapping, and the badge branch exist — the contract is
  complete on both ends and pinned by tests (`tests/test_contracts.py`, the
  frontend's parse test).
- `CorpusPathVerifier` exists as the citation-existence check for the day
  citations can point beyond `rag.search`'s own rows; it is not wired, and its
  query is tested against the live schema (integration tests).
- The NLI harness lives *offline* in the evals, where CPU and RAM are free, as
  documented behavior for the future JobFinder service (ADR 0008).
- The chat `done` emitters consult `configured_verifier()` and report its
  verdict — `False` by default, honestly tested in `test_chat_loop.py`.

## The upgrade paths

1. **JobFinder's NLI endpoint** (per ADR 0008) becomes the verifier behind the
   same `SourceVerifier` interface. This is the intended path; the harness in
   `evals/` is the behavioral spec, done offline.
2. A stricter prompt trick — e.g. a structured `cited_claims` list from the
   model per turn — would give the verifier sentence-sized premises and likely
   remove the neutral bias. That changes the loop's prompt budget for every
   answer; it was not justified before a remote verifier exists to compare to.

## Why not ship the badge as "unverified" instead

A visible badge that says "not verified" would be visually equivalent to a
spinner that never resolves, on every answer, forever. Its absence is quieter
and no less honest. The citations remain the primary provenance surface.
