# 0008 — Idle connectors: typed seams for two services that do not exist yet

Checkpoint 1, and the one decision this checkpoint exists to record. The user
asked for "idle connector seams, so the future part can be added": the Job
Finder app and the ThirdBrain notes corpus are planned services, neither has an
API contract yet, but their plug-in points are now typed, mocked, and tested in
`app/services/connectors.py`.

## The tension, stated plainly

This is the one place in the codebase that an interface with one
implementation and zero call sites exists on purpose. The ponytail ladder says
no Protocols without a second implementation, and it is right in general —
here the interface *is* the deliverable. Writing the seam now means that when
the contract arrives, the wiring is deleting two fixture classes and adding two
HTTP classes behind identical typing; skipping it instead means the shape gets
invented under time pressure against a live webhook. ADR 0006 documents how
decisions made under that kind of pressure go when nobody stops to type the
boundary first.

What makes it cheap rather than speculative: no network code, no credentials,
no config keys — nothing to maintain or misconfigure today, and nothing that
can be wrong in production.

## The shape

Two `Protocol` classes, each with one method:

- `JobFinderConnector.verify_grounding(answer, snippets) -> GroundingVerdict` —
  the NLI check, when the service exists. Job listing lookups join as a second
  method on the same class; they are not pre-typed, because two guesses about
  one contract are worse than one.
- `ThirdBrainConnector.search(query, limit) -> ThirdBrainReply` — the notes
  corpus, once it leaves this repository.

Fixture implementations return deterministic, labelled, obviously-fake data
and satisfy their Protocols (`runtime_checkable` makes that claim executable
in a test). Everything the future HTTP classes will receive is shaped through
one function per connector: `shape_verdict` and `shape_hits`. Those functions
carry github.py's untrusted-data rule — capped, labelled, failures as results
rather than exceptions — and the tests pin their behaviour against a timeout,
a non-200 and malformed JSON, so a bug cannot live in the gap between the
fixture and the wire.

## The relation to the local verifier (checkpoint 3)

Checkpoint 3 introduces a *local* check, `SourceVerifier` +
`CorpusPathVerifier`: does every cited `source_path` resolve to an ingested
chunk? Both futures describe grounding, so to avoid one concept having two
interfaces, the split is by distance:

- The local verifier answers "does the citation exist?" — it runs in-process
  against the database, needs no service, and is what the shipped badge would
  use if it were wired (it is not; see the checkpoint's ADR-able decision that
  the badge stays dark).
- `JobFinderConnector.verify_grounding` answers "is the answer actually true?"
  — a property only a model can judge, which is why it lives behind a service
  boundary.

No adapter joins them today. When the JobFinder API is callable, a three-line
adapter implements the local interface by calling the connector; until then an
adapter wraps nothing and teaches nobody anything.

## Rejected alternatives

- **Live stubs with real keys and a fake endpoint** — invites half-finished
  services to be signed off as done, and needs a secret on day one.
- **No seam at all, "add it when you need it"** — the connector becomes a
  peer-to-peer call from `services/chat.py` the day Job Finder lands, bypassing
  the shaper and its caps, because nothing in the type system stops it.
- **Pre-typing the job-listings endpoint too** — one contract guess per
  checkpoint is the cap. A second guess doubles the surface that has to be
  rewritten when the real API shows up.
