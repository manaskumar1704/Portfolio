"""The tool loop, with a fake provider.

These are the tests that matter most in the project. The loop is the thing a
recruiter watches working, and its failure modes are silent: an infinite loop, a
lost tool result, a registry bypass. None of those raise. They just produce a
wrong answer.

The fake client is deliberately dumb — it returns whatever the test hands it —
so every assertion is about the loop's behaviour rather than about a provider's
tool-calling quirks.
"""

from collections.abc import AsyncIterator, Sequence
from dataclasses import dataclass, field
from typing import Any

from app.services.chat import StreamEvent, run_chat_turn
from app.services.llm import ChatMessage, ToolCall, ToolResult, ToolSpec, TurnResult


@dataclass
class ScriptedClient:
    """Returns turns from a list, one per leg. Records what it was asked."""

    turns: list[TurnResult]
    calls: list[dict[str, Any]] = field(default_factory=list)

    async def stream(
        self,
        *,
        messages: Sequence[ChatMessage],
        tools: Sequence[ToolSpec],
        system_instruction: str,
        previous_interaction_id: str | None = None,
        tool_results: Sequence[ToolResult] = (),
    ) -> AsyncIterator[TurnResult]:
        index = len(self.calls)
        self.calls.append(
            {
                "messages": list(messages),
                "tools": [t.name for t in tools],
                "system": system_instruction,
                "previous_interaction_id": previous_interaction_id,
                "tool_results": list(tool_results),
                "n_results": len(tool_results),
            }
        )
        yield self.turns[index] if index < len(self.turns) else TurnResult(text="done.")


async def collect(client: ScriptedClient, message: str, history=None) -> list[StreamEvent]:
    return [event async for event in run_chat_turn(client, message, history)]


async def test_answers_without_calling_a_tool() -> None:
    """A plain question gets prose and nothing else."""
    client = ScriptedClient([TurnResult(text="He ships RAG systems.")])

    events = await collect(client, "what does he build?")

    assert [e.kind for e in events] == ["delta", "done"]
    assert events[0].data["text"] == "He ships RAG systems."


async def test_runs_a_tool_then_answers() -> None:
    """The whole point: model calls a tool, the answer comes back informed."""
    client = ScriptedClient(
        [
            TurnResult(
                text="",
                tool_calls=[ToolCall(id="c1", name="echo", arguments={"text": "hi"})],
                interaction_id="int-1",
            ),
            TurnResult(text="He said hi.", interaction_id="int-2"),
        ]
    )

    events = await collect(client, "say hi")

    assert [e.kind for e in events] == ["tool_call", "tool_result", "delta", "done"]
    assert events[1].data["ok"] is True
    assert events[1].data["result"] == {"echoed": "hi"}


async def test_tool_result_is_sent_back_to_the_model() -> None:
    """The leg after a tool call must carry the result and the interaction id.

    This is the bug the loop exists to prevent: dropping the result leaves the
    model with no record of its own request, and it re-calls until the cap.
    """
    client = ScriptedClient(
        [
            TurnResult(
                tool_calls=[ToolCall(id="c1", name="echo", arguments={"text": "x"})],
                interaction_id="int-1",
            ),
            TurnResult(text="ok", interaction_id="int-2"),
        ]
    )

    await collect(client, "say x")

    assert len(client.calls) == 2
    second = client.calls[1]
    assert second["n_results"] == 1
    assert second["tool_results"][0].name == "echo"
    assert second["previous_interaction_id"] == "int-1"


async def test_unregistered_tool_does_not_crash_the_stream() -> None:
    """A model that invents a tool gets an error result, not an exception.

    The stream has to survive it: a 500 mid-answer leaves the visitor staring at
    a spinner with half an answer on screen.
    """
    client = ScriptedClient(
        [
            TurnResult(
                tool_calls=[ToolCall(id="c1", name="drop_database", arguments={})],
                interaction_id="int-1",
            ),
            TurnResult(text="I cannot do that.", interaction_id="int-2"),
        ]
    )

    events = await collect(client, "drop everything")

    result = next(e for e in events if e.kind == "tool_result")
    assert result.data["ok"] is False
    assert "no such tool" in result.data["error"]
    assert events[-1].kind == "done"


async def test_bad_arguments_are_reported_not_raised() -> None:
    """Missing required arguments produce a complaint the model can act on."""
    client = ScriptedClient(
        [
            TurnResult(
                tool_calls=[ToolCall(id="c1", name="echo", arguments={})],
                interaction_id="int-1",
            ),
            TurnResult(text="sorry", interaction_id="int-2"),
        ]
    )

    events = await collect(client, "echo nothing")

    result = next(e for e in events if e.kind == "tool_result")
    assert result.data["ok"] is False
    assert "invalid arguments" in result.data["error"]


async def test_infinite_tool_loop_is_capped() -> None:
    """A model that keeps calling the same tool must not spin forever.

    Each scripted leg asks for the tool again, which is the pathological case:
    without the cap this is an unbounded loop on a free-tier request.
    """
    endless = TurnResult(
        tool_calls=[ToolCall(id="c1", name="echo", arguments={"text": "again"})],
        interaction_id="int-1",
    )
    client = ScriptedClient([endless, endless, endless, endless, endless, endless])

    events = await collect(client, "loop forever")

    assert events[-1].kind == "done"
    assert events[-1].data["sources"] == []
    # The cap message has to reach the visitor, not just the log.
    deltas = " ".join(e.data["text"] for e in events if e.kind == "delta")
    assert "tool limit" in deltas


async def test_history_is_forwarded_to_the_provider() -> None:
    """The client owns the conversation; the server replays what it was given."""
    client = ScriptedClient([TurnResult(text="ok")])
    history = [
        ChatMessage(role="user", text="hi"),
        ChatMessage(role="bot", text="hello"),
    ]

    await collect(client, "and now?", history)

    forwarded = client.calls[0]["messages"]
    assert [m.text for m in forwarded] == ["hi", "hello", "and now?"]


async def test_system_instruction_is_always_supplied() -> None:
    """The guardrails live here, so an empty one would be a silent downgrade."""
    client = ScriptedClient([TurnResult(text="ok")])

    await collect(client, "hi")

    system = client.calls[0]["system"]
    assert "portfolio" in system.lower()
    assert "never invent" in system.lower()


def test_system_instruction_teaches_the_abstention_rule() -> None:
    """`found: false` has to mean "say you don't know", not "search again".

    Observed before this was written: a question about the corpus's subject got
    answered with "I do not know what certifications Manas has", because the
    retrieved passages named a different person and the model concluded the whole
    corpus was irrelevant.
    """
    from app.services.chat import SYSTEM_INSTRUCTION

    lowered = SYSTEM_INSTRUCTION.lower()
    assert "found: false" in lowered
    assert "not in the corpus" in lowered
    assert "fixture data" in lowered


async def test_prose_before_a_tool_call_is_not_replayed() -> None:
    """A model that narrates, then calls a tool, must not repeat its narration.

    Observed against the live API: `output_text` is the last run of text in the
    final response, which is empty when that response is only a function call.
    A model that says "let me look that up" and then calls a tool would
    otherwise have that line repeated verbatim in the answer.
    """
    client = ScriptedClient(
        [
            TurnResult(
                text="Let me check that.",
                tool_calls=[ToolCall(id="c1", name="echo", arguments={"text": "x"})],
                interaction_id="int-1",
            ),
            TurnResult(text="Here is the answer.", interaction_id="int-2"),
        ]
    )

    events = await collect(client, "look it up")

    deltas = [e.data["text"] for e in events if e.kind == "delta"]
    assert deltas == ["Let me check that.", "Here is the answer."]


async def test_a_tool_call_leg_with_no_text_emits_no_delta() -> None:
    """The common shape: leg one is a bare tool call, leg two is the answer."""
    client = ScriptedClient(
        [
            TurnResult(
                tool_calls=[ToolCall(id="c1", name="echo", arguments={"text": "x"})],
                interaction_id="int-1",
            ),
            TurnResult(text="done answering", interaction_id="int-2"),
        ]
    )

    events = await collect(client, "anything")

    assert [e.kind for e in events] == ["tool_call", "tool_result", "delta", "done"]


async def test_no_error_text_leaks_to_the_visitor() -> None:
    """A failing tool's traceback must never become part of an answer."""
    client = ScriptedClient(
        [
            TurnResult(
                tool_calls=[ToolCall(id="c1", name="echo", arguments={"text": "x" * 600})],
                interaction_id="int-1",
            ),
            TurnResult(text="handled", interaction_id="int-2"),
        ]
    )

    events = await collect(client, "too long")

    everything = " ".join(str(e.data) for e in events)
    assert "Traceback" not in everything
    assert "pydantic" not in everything.lower()


async def test_sources_are_collected_for_the_done_event() -> None:
    """Citations the tools reported travel to the client for rendering."""
    client = ScriptedClient(
        [
            TurnResult(
                tool_calls=[ToolCall(id="c1", name="echo", arguments={"text": "x"})],
                interaction_id="int-1",
            ),
            TurnResult(text="here you go", interaction_id="int-2"),
        ]
    )

    events = await collect(client, "anything")

    assert events[-1].kind == "done"
