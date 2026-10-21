"""Source verification: whether a streamed answer is grounded in what it cited.

## The three measurements that shaped this

- **The model does not cite in prose.** Five live answers contained no `[n]`
  markers and no paths, so any check has to run on the `sources` list the tool
  loop collected — not on the answer text. There is nothing in the text to find.
- **No cheap local check discriminates.** `source_path` membership would, but
  only answers the question "does the citation exist?", never "is the claim
  true?". An NLI cross-encoder asked the true question over chunk-sized
  premises answered *neutral* for everything, and neither cosine ranges nor
  lexical coverage separated supported answers from fabricated ones. The NLI
  harness survives, offline, as `evals/test_groundedness_nli.py`; it is not in
  the request path (ADR 0009).
- **So nothing earns the badge yet.** The badge contract is honest by
  construction: `done.sources_verified` is `False` until a verifier is both
  wired and satisfied, and this release wires none of them.

## What exists

`SourceVerifier` is the Protocol. `CorpusPathVerifier` is the only real
implementation, and it answers the existence question: every cited
`source_path` must resolve to an ingested chunk. It is not wired today either —
it exists so the day something starts citing computed or aggregated paths, the
check under the badge is one assignment away, and so its query is testable
against the live schema now, not after that day.

The model-shaped check (is the answer actually true?) belongs to the JobFinder
service's NLI endpoint when it exists; it drops into this same Protocol (ADR
0008). When it is trusted, wire it by assigning `_VERIFIER` and nothing else in
`services/chat.py` has to change.
"""

from collections.abc import Sequence
from dataclasses import dataclass
from typing import Protocol, runtime_checkable

from sqlalchemy import text

from app.core.logging import get_logger
from app.db import pool

log = get_logger(__name__)


@dataclass(frozen=True)
class SourceVerdict:
    """One verifier's answer about one streamed answer.

    `verified` is the only word the badge reads; `checker` and `note` exist so
    a log line can say who decided and why.
    """

    verified: bool
    checker: str
    note: str


@runtime_checkable
class SourceVerifier(Protocol):
    """The contract any verification backend satisfies, locally or remote."""

    async def verify(self, answer: str, sources: Sequence[str]) -> SourceVerdict:
        """Judge `answer` against `sources`; never raise, fail closed."""


# The wire point. Nothing is assigned here on purpose: an unassigned verifier
# is how the badge stays dark while the contract is tested from both ends.
_VERIFIER: SourceVerifier | None = None


def configured_verifier() -> SourceVerifier | None:
    """The verifier wired for this process, or None. Never raises."""
    return _VERIFIER


_PATH_SQL = "SELECT DISTINCT source_path FROM chunks WHERE source_path = ANY(:paths)"


class CorpusPathVerifier:
    """The citation-existence check: every cited path was ingested from it.

    Useful the moment citations can point anywhere but the corpus — an
    aggregation, a computed reference, a second corpus. Against today's loop,
    whose sources come from `rag.search`'s own rows, it verifies by
    construction; the value is the floor it sets below the model-shaped check.
    """

    async def verify(self, answer: str, sources: Sequence[str]) -> SourceVerdict:
        """Fail closed on empty citations, unknown paths, and query errors."""
        if not sources:
            return SourceVerdict(False, "corpus_path", "no sources were cited")

        try:
            async with pool.session_scope() as session:
                rows = (await session.execute(text(_PATH_SQL), {"paths": list(sources)})).fetchall()
        except Exception:
            # A verifier that raises breaks the answer the visitor is watching;
            # the contract is results, and the safe result is "not verified".
            log.exception("corpus path verification query failed")
            return SourceVerdict(False, "corpus_path", "the verification query failed")

        known = {row.source_path for row in rows}
        unknown = sorted(set(sources) - known)
        if unknown:
            return SourceVerdict(
                False,
                "corpus_path",
                f"cited {len(unknown)} path(s) not in the corpus, first: {unknown[0]}",
            )

        return SourceVerdict(True, "corpus_path", "every cited path resolves to an ingested chunk")
