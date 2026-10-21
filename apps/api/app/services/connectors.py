"""Idle connectors: the plug-in points for two services that do not exist yet.

## What a connector is, and is not

Two future services have a shape in this codebase before either has an API:

- **JobFinder** — the author's job-matching app. Its first service to this site
  is grounding verification: given an answer and the snippets behind it, say
  whether the snippets support the answer. Job listings join the same class
  when the API exists (ADR 0008).
- **ThirdBrain** — the notes corpus this agent would search, once it moves out
  of this repository. `search` is the only thing this site would ask of it.

There is no network code here, no credentials, no config keys and no caller in
the request path. The value is narrower than it looks: when the real contracts
arrive, the wiring is replacing the fixture class with an HTTP class behind the
same Protocol, and no call site anywhere has to change. ADR 0008 records why a
Protocol whose only implementation is a fixture was written at all.

## The untrusted-data rule (mirrors `github.py`)

A connector's payload is third-party text that would reach the model inside a
prompt. So every response is shaped through one function per connector, in this
file, on its way out: capped, and labelled with its origin. Failures arrive as
results — `supported=False`, `hits=()` with an `error` — never as exceptions, on
the same rule as the tools: a raise mid-answer breaks the turn the visitor is
watching.

When the real HTTP classes are written they must feed their raw responses
through these same shapers; the tests pin what the shapers do with a timeout, a
non-200 and garbage JSON, so a bug cannot live in the gap between the fixture
and the wire.
"""

from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any, Protocol, runtime_checkable

# Caps, why: a connector's reply is prompt material, and an unlimited one is a
# bill and an attack surface at once. Same budget logic as `README_MAX_CHARS`.
NOTE_MAX_CHARS = 280
HIT_TEXT_MAX_CHARS = 800
HIT_COUNT_MAX = 5


def _clip(text: str, limit: int) -> str:
    """Cap at `limit`, saying so, in the marker style `clean_readme` uses."""
    if len(text) <= limit:
        return text
    return f"{text[:limit].rstrip()}\n[truncated, {len(text)} characters total]"


@dataclass(frozen=True)
class GroundingVerdict:
    """The answer one service gives about one answer of ours.

    `supported=False` is deliberately the only form a failure can take: the
    provider name stays on the verdict, and `note` carries the human reason
    (the service's own words when it answered, ours when it did not).
    """

    supported: bool
    provider: str
    note: str


@dataclass(frozen=True)
class SearchHit:
    """One retrieved item, labelled with where it claims to come from."""

    source: str
    label: str
    text: str


@dataclass(frozen=True)
class ThirdBrainReply:
    """Search results as data. `error` explains an empty `hits`, nothing else."""

    hits: tuple[SearchHit, ...]
    error: str | None


def shape_verdict(
    provider: str, payload: Any = None, failure: str | None = None
) -> GroundingVerdict:
    """One provider response → one verdict; anything ambiguous is "unsupported".

    `failure` is what the HTTP layer observed when there is no usable reply at
    all — a timeout is a string here, not an exception. The three shapes it can
    meet land identically: a verdict that says not-supported, keeps the
    provider's name, and explains in words a visitor can read.
    """
    if failure is not None:
        return GroundingVerdict(False, provider, _clip(failure, NOTE_MAX_CHARS))

    if not isinstance(payload, dict):
        return GroundingVerdict(
            False, provider, "the grounding service did not send a usable reply"
        )

    supported = payload.get("supported")
    if not isinstance(supported, bool):
        # The malformed-JSON case: the service answered, but its answer means
        # nothing. Never guess whether "certain" counts as a yes.
        return GroundingVerdict(False, provider, "the grounding service sent a malformed reply")

    note = payload.get("note")
    if not isinstance(note, str) or not note.strip():
        note = "(the service explained nothing)"

    return GroundingVerdict(supported, provider, _clip(note, NOTE_MAX_CHARS))


def shape_hits(source: str, payload: Any = None, failure: str | None = None) -> ThirdBrainReply:
    """One provider response → a reply; a failure is an empty list with a reason."""
    if failure is not None:
        return ThirdBrainReply((), _clip(failure, NOTE_MAX_CHARS))

    if not isinstance(payload, list):
        return ThirdBrainReply((), "the notes service did not send a usable reply")

    entries = payload[:HIT_COUNT_MAX]
    for entry in entries:
        if not isinstance(entry, dict) or not isinstance(entry.get("text"), str):
            # All-or-nothing: a list whose middle entry is garbage is one
            # request's answer, and half an answer is not a faithful one.
            return ThirdBrainReply((), "the notes service sent a malformed reply")

    hits = tuple(
        SearchHit(
            source=source,
            label=str(entry.get("label") or ""),
            text=_clip(entry["text"], HIT_TEXT_MAX_CHARS),
        )
        for entry in entries
    )
    return ThirdBrainReply(hits, None)


@runtime_checkable
class JobFinderConnector(Protocol):
    """The contract the JobFinder API will satisfy, when it exists.

    Job listing lookups join here as a second method, per ADR 0008. Nothing
    else in the codebase depends on this yet — that is what "idle" means.
    """

    async def verify_grounding(self, answer: str, snippets: Sequence[str]) -> GroundingVerdict:
        """Whether `snippets` support `answer`, in the provider's own judgement."""


@runtime_checkable
class ThirdBrainConnector(Protocol):
    """The contract a self-hosted notes service would satisfy for this site."""

    async def search(self, query: str, limit: int = HIT_COUNT_MAX) -> ThirdBrainReply:
        """Labelled excerpts matching `query`, at most `limit` of them."""


# --- The fixtures -------------------------------------------------------------
#
# Deterministic, obviously-fake payloads, shaped exactly like the future wire
# responses so the shaper tests below are meaningful for the real classes too.


_JOBFINDER_FIXTURE: dict[str, Any] = {
    "supported": True,
    "note": "fixture data: no JobFinder API is connected yet",
}
_THIRDBRAIN_FIXTURE: list[dict[str, Any]] = [
    {
        "label": "fixture/notes.md",
        "text": "Fixture excerpt. ThirdBrain is not connected, so nothing here is real.",
    },
    {
        "label": "fixture/journal.md",
        "text": "Fixture excerpt. This item exists to prove the labelling and the cap.",
    },
]


class FixtureJobFinder:
    """The offline stand-in until the JobFinder API has a contract."""

    async def verify_grounding(self, answer: str, snippets: Sequence[str]) -> GroundingVerdict:
        return shape_verdict("jobfinder", dict(_JOBFINDER_FIXTURE))


class FixtureThirdBrain:
    """The offline stand-in until the notes service has a contract."""

    async def search(self, query: str, limit: int = HIT_COUNT_MAX) -> ThirdBrainReply:
        return shape_hits(
            "thirdbrain",
            list(_THIRDBRAIN_FIXTURE)[: max(0, min(limit, HIT_COUNT_MAX))],
        )
