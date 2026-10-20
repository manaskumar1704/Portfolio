"""Optional Langfuse tracing. One turn, one span, honest metadata.

## What this module traces, and what it refuses to (ADR 0010)

Per chat turn: provider-leg duration and token usage, tool outcomes (name, ok,
duration), and whether the final answer had sources at all. Never: message
text in either direction, draft bodies, approval tokens or their hashes, API
keys, or IP hashes. The visitor's words stay on this site's stack; the trace
is the incident report's skeleton, not the interview transcript.

The no-op path is load-bearing: with no keys configured — every local
checkout's default — nothing here constructs a client, opens a span, or puts
a byte or thread of work anywhere. The chat loop calls this module at four
points, and all four are guarded by the first settings read inside
`TurnTrace`, so the unconfigured cost is four `if not span: return`s.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from app.core.config import get_settings
from app.core.logging import get_logger

if TYPE_CHECKING:
    from langfuse import Langfuse

log = get_logger(__name__)

# Created once, on the first enabled turn, and never torn down — a process
# that traces at all keeps one HTTP pool for the exporter, like the one the
# provider client keeps. `None` with keys configured means creation failed
# this turn; the next turn tries again.
_client: Langfuse | None = None


def _langfuse() -> Langfuse:
    """The singleton client, created on first use so checks without keys
    never pay the import. Import happens inside, for the same reason."""
    global _client
    if _client is None:
        from langfuse import Langfuse

        settings = get_settings()
        _client = Langfuse(
            public_key=settings.langfuse_public_key,
            secret_key=settings.langfuse_secret_key,
            host=settings.langfuse_host,
            timeout=10,
        )
    return _client


class TurnTrace:
    """One chat turn's span — or four no-ops when tracing is off.

    Everything the chat loop calls is one line and cannot raise: a tracer bug
    must never reach the visitor's stream, so every method swallows and logs.
    """

    __slots__ = ("_span",)

    def __init__(self) -> None:
        self._span = None
        settings = get_settings()
        if not settings.langfuse_enabled:
            # ADR 0010: the contract point. No keys, no SDK import, no client,
            # no span. What follows is all `if self._span is None: return`.
            return
        try:
            self._span = _langfuse().start_observation(name="chat-turn")
        except Exception as exc:
            log.warning("tracing unavailable this turn: %s", type(exc).__name__)
            self._span = None

    def leg(self, seconds: float, prompt_tokens: int, completion_tokens: int) -> None:
        """One provider leg: its duration and the usage it reported.

        Duration is the wall-clock the loop measured with `monotonic`, so it is
        honest even though the span itself starts and ends in microseconds.
        """
        if self._span is None:
            return
        try:
            self._span.start_observation(
                name="provider-leg",
                usage_details={"input": prompt_tokens, "output": completion_tokens},
                metadata={"duration_ms": round(seconds * 1000)},
            ).end()
        except Exception as exc:
            log.warning("trace leg failed: %s", type(exc).__name__)

    def tool(self, name: str, ok: bool, seconds: float) -> None:
        """One tool outcome. Class, not content: ok plus how long it took."""
        if self._span is None:
            return
        try:
            child = self._span.start_observation(
                name=name,
                as_type="tool",
                metadata={"duration_ms": round(seconds * 1000)},
                level="DEFAULT" if ok else "ERROR",
            )
            child.end()
        except Exception as exc:
            log.warning("trace tool failed: %s", type(exc).__name__)

    def finish(self, sources_count: int, text_length: int) -> None:
        """Close the turn: whether sources existed, and how much prose there was.

        Presence counts, words never: `text_length` is a shape, not a text.
        """
        if self._span is None:
            return
        try:
            self._span.update(
                metadata={
                    "sources_count": sources_count,
                    "sources_present": sources_count > 0,
                    "text_length": text_length,
                }
            )
            self._span.end()
            _langfuse().flush()
        except Exception as exc:
            log.warning("trace finish failed: %s", type(exc).__name__)
