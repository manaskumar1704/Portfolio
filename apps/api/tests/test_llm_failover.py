"""Behaviour tests for `FailoverClient`.

Fakes only, no network. The wrapper's contract is about attempt counts and what
reaches the caller — the providers' wire formats have their own tests in
`test_llm.py`.
"""

import asyncio
from collections.abc import AsyncIterator

import pytest

from app.services.llm import FailoverClient, TurnResult


class Stub:
    """A provider that fails `fails` times, then answers. Counts its calls."""

    def __init__(self, text: str, fails: int) -> None:
        self.text = text
        self.fails = fails
        self.calls = 0

    async def stream(self, **_: object) -> AsyncIterator[TurnResult]:
        # An exception before the yield is the whole point: the wrapper may
        # retry a leg precisely because nothing has reached the caller yet.
        self.calls += 1
        if self.fails:
            self.fails -= 1
            raise RuntimeError("provider down")
        yield TurnResult(text=self.text, interaction_id="i-1")


async def consume(wrapped: FailoverClient) -> list[TurnResult]:
    kwargs = {
        "messages": [],
        "tools": [],
        "system_instruction": "s",
        "previous_interaction_id": None,
        "tool_results": (),
    }
    return [turn async for turn in wrapped.stream(**kwargs)]


async def test_primary_answers_wheel_fallback_never_called() -> None:
    primary = Stub("from primary", fails=0)
    fallback = Stub("from fallback", fails=0)

    turns = await consume(FailoverClient(primary, fallback, max_attempts=2))

    assert [turn.text for turn in turns] == ["from primary"]
    assert primary.calls == 1
    assert fallback.calls == 0


async def test_primary_retried_within_the_attempt_budget() -> None:
    primary = Stub("recovered alone", fails=1)  # fails once, succeeds second try
    fallback = Stub("unused", fails=0)

    turns = await consume(FailoverClient(primary, fallback, max_attempts=2))

    assert [turn.text for turn in turns] == ["recovered alone"]
    assert primary.calls == 2
    assert fallback.calls == 0


async def test_switches_after_the_budget_is_spent() -> None:
    primary = Stub("never lands", fails=2)  # max_attempts=2 → budget exhausted
    fallback = Stub("saved by groq-class adapter", fails=0)

    turns = await consume(FailoverClient(primary, fallback, max_attempts=2))

    assert [turn.text for turn in turns] == ["saved by groq-class adapter"]
    assert primary.calls == 2
    assert fallback.calls == 1


async def test_with_no_fallback_the_primary_gets_all_the_attempts() -> None:
    primary = Stub("late but fine", fails=2)
    turns = await consume(FailoverClient(primary, None, max_attempts=3))
    assert turns[0].text == "late but fine"
    assert primary.calls == 3


async def test_when_both_exhaust_the_last_error_reaches_the_router() -> None:
    """The router already frames exceptions, so the wrapper must not swallow
    the final failure into an empty answer."""
    primary = Stub("p", fails=99)
    fallback = Stub("f", fails=99)

    with pytest.raises(RuntimeError):
        await consume(FailoverClient(primary, fallback, max_attempts=2))

    assert primary.calls == 2
    assert fallback.calls == 2


async def test_cancellation_is_never_caught_and_never_retried() -> None:
    """A visitor closing the tab kills the request outright.

    The stub stays an async generator (one unreachable `yield`) so the wrapper
    receives the CancelledError from iteration, the same way a real adapter
    raises it mid-leg.
    """

    class Cancelled(Stub):
        async def stream(self, **_: object) -> AsyncIterator[TurnResult]:
            self.calls += 1
            raise asyncio.CancelledError
            yield TurnResult()  # marker only: this must stay an async generator

    cancelled = Cancelled("p", fails=0)

    with pytest.raises(asyncio.CancelledError):
        await consume(FailoverClient(cancelled, None, max_attempts=2))

    assert cancelled.calls == 1  # no second attempt on a cancelled turn
